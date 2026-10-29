from solver import sum_squares

for values in ([], [0], [-3, 4], list(range(10000))):
    assert sum_squares(values) == sum(value ** 2 for value in values)
print("Public sum-of-squares checks passed")
