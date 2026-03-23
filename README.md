# PyPM

**PyPM** is an open-source Python library for **pattern mining**.  
It is designed to provide a broad, research-oriented, and reproducible Python framework covering major pattern-mining families, including:

- **Itemset mining**
- **High-utility itemset mining**
- **High-utility sequential pattern mining**
- **Sequential pattern mining**

PyPM is developed with two main goals:

1. to provide a **rich Python framework** that covers many influential pattern-mining algorithms in a unified environment;
2. to provide **publicly available code and testing datasets** for transparent and reproducible research.

## Why PyPM?

Pattern mining has produced a large number of algorithms over the last three decades, but the available Python ecosystem is still fragmented. PyPM aims to reduce this gap by offering:

- a unified Python environment for multiple pattern-mining families;
- broad algorithmic coverage;
- validation against **SPMF** reference implementations;
- public release of source code and testing data;
- a foundation for teaching, benchmarking, and future research.

## Current Coverage

At the current stage, PyPM includes **144 implemented entries**:

| Category | Implemented |
|---|---:|
| Itemset mining | 42 |
| High-utility itemset mining | 70 |
| High-utility sequential pattern mining | 3 |
| Sequential pattern mining | 29 |
| **Total** | **144** |

Planned future extensions include:

- association rule mining
- sequential rule mining
- sequence prediction
- periodic pattern mining
- episode mining

## Validation

A key design principle of PyPM is **implementation reliability**.

Each Python implementation is validated against the corresponding **Java implementation in SPMF** under:

- the same input datasets,
- the same parameter settings,
- and the same experimental conditions.

The returned pattern sets and associated values (such as support or utility) are compared to ensure matching outputs.

## Repository Structure

The organization of the project is as follows:

```text
pypm/
├── pypm/                # source code
├── datasets/            # testing datasets
├── examples/            # usage examples / notebooks / scripts
├── tests/               # validation and unit tests
├── docs/                # documentation
└── README.md
