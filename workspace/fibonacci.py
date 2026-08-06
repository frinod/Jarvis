# Fibonacci number calculator

def calculate_fibonacci(n):
    # Handle invalid input
    if n < 0:
        raise ValueError("Input must be a non-negative integer")
    # Base cases
    if n == 0:
        return 0
    elif n == 1:
        return 1
    # Recursive case
    else:
        return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

# Example usage
if __name__ == "__main__":
    n = 10
    result = calculate_fibonacci(n)
    print(f"The {n}th Fibonacci number is: {result}")