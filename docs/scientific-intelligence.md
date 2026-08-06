# Scientific Intelligence Module

JARVIS OS includes a scientific computation engine supporting:

## Mathematics
- Symbolic math via SymPy (calculus, algebra, linear algebra)
- Numerical computation via NumPy/SciPy
- Statistics and probability

## Physics & Engineering
- Unit conversion and dimensional analysis
- Thermodynamics calculations
- Circuit analysis
- Fluid mechanics basics
- Material property lookups

## Chemistry
- Molecular formula parsing
- Reaction balancing
- Property lookups

## Usage

The scientific agent is invoked automatically when JARVIS detects a technical query.
You can also explicitly request scientific computation:

> "Calculate the eigenvalues of [[1,2],[3,4]]"
> "Solve the differential equation dy/dx = 2x + y"
> "What's the Reynolds number for water at 2 m/s in a 5cm pipe?"

## Extension

Add new scientific capabilities via plugins or by extending the `ScientificAgent` class.
