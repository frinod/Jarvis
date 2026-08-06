# Python script to select YAML file for ADO pipeline
import os
import argparse

# Define arguments
parser = argparse.ArgumentParser(description='Select YAML file for ADO pipeline')
parser.add_argument('--file', type=str, help='Path to YAML file')
args = parser.parse_args()

# Check if file exists
if not os.path.isfile(args.file):
    print(f'Error: File {args.file} not found')
    exit(1)

# Print selected YAML file
print(f'Selected YAML file: {args.file}')