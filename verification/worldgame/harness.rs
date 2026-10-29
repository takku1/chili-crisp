//! Owner-controlled entry point. Candidate code supplies the library only.
use mote_core::{PlanetSpec, planet::Planet, orbit::AstronomySpec, ocean, numerics};
use std::io::{self, Write};

fn emit(values: &[f64]) -> io::Result<()> {
    let mut out = io::BufWriter::new(io::stdout().lock());
    out.write_all(b"CCFIELDS1")?;
    out.write_all(&(values.len() as u64).to_le_bytes())?;
    for value in values { out.write_all(&value.to_le_bytes())?; }
    out.flush()
}

fn main() -> Result<(), String> {
    let args: Vec<_> = std::env::args().collect();
    let mut values = Vec::new();
    match args.get(1).map(String::as_str) {
        Some("ocean") => {
            let seed: u64 = args.get(2).ok_or("seed required")?.parse().map_err(|_| "bad seed")?;
            let scale: f64 = args.get(3).ok_or("radius scale required")?.parse().map_err(|_| "bad scale")?;
            if !scale.is_finite() || !(0.5..=2.0).contains(&scale) { return Err("scale out of range".into()); }
            let mut spec = PlanetSpec::default();
            spec.seed = seed;
            spec.radius_m *= scale;
            let planet = Planet::generate(spec);
            let orbit = AstronomySpec::default().validated()?;
            let flow = ocean::OceanCirculation::generate(&planet, &orbit)?;
            if flow.width != 180 || flow.height != 80 || flow.depths_m.len() != 14400 {
                return Err("unexpected circulation layout".into());
            }
            values.extend_from_slice(&flow.depths_m);
            for season in 0..4 {
                if flow.seasonal_psi[season].len() != 14580 || flow.seasonal_surface_psi[season].len() != 14580 {
                    return Err("unexpected seasonal layout".into());
                }
                values.extend_from_slice(&flow.seasonal_psi[season]);
                values.extend_from_slice(&flow.seasonal_surface_psi[season]);
            }
        }
        Some("manufactured") => {
            let n: usize = args.get(2).ok_or("size required")?.parse().map_err(|_| "bad size")?;
            if !(5..=65).contains(&n) { return Err("grid size out of range".into()); }
            let h = 1.0 / (n - 1) as f64;
            let mut rows = vec![numerics::Stencil { diagonal: 1.0, neighbours: [(0, 0.0);4] }; n*n];
            let mut rhs = vec![0.0; n*n];
            for y in 1..n-1 { for x in 1..n-1 {
                let i = y*n+x;
                rows[i] = numerics::Stencil { diagonal: 4.0/(h*h),
                    neighbours: [(i-1,1.0/(h*h)),(i+1,1.0/(h*h)),(i-n,1.0/(h*h)),(i+n,1.0/(h*h))] };
                rhs[i] = 2.0*std::f64::consts::PI.powi(2)
                    *(std::f64::consts::PI*x as f64*h).sin()
                    *(std::f64::consts::PI*y as f64*h).sin();
            }}
            values.resize(n*n, 0.0);
            // The verifier checks values; it does not trust the report.
            numerics::solve(&rows, &rhs, &mut values, 20000, 1e-10)?;
        }
        _ => return Err("expected ocean or manufactured".into()),
    }
    emit(&values).map_err(|error| error.to_string())
}
