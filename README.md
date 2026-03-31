# pypatternminer

**pypatternminer** is an open-source Python library for **pattern mining**. It provides a broad, research-oriented, and reproducible framework for major pattern-mining families, including:

- **Itemset mining**
- **High-utility itemset mining**
- **High-utility sequential pattern mining**
- **Sequential pattern mining**

The project is developed with two main goals:

1. to provide a **comprehensive Python framework** covering many influential pattern-mining algorithms in a unified environment;
2. to provide **publicly available code and testing datasets** to support transparent and reproducible research.

## Why pypatternminer?

Pattern mining has produced a large number of important algorithms over the past three decades, but the Python ecosystem remains relatively fragmented. **pypatternminer** aims to help bridge this gap by offering:

- a unified Python environment for multiple pattern-mining families;
- broad algorithmic coverage;
- validation against **SPMF** reference implementations;
- public access to source code and testing datasets;
- a foundation for teaching, benchmarking, and future research.

## Current Coverage

At the current stage, **pypatternminer** includes **144 implemented entries**:

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

A key design principle of **pypatternminer** is **implementation reliability**.

Each Python implementation is validated against the corresponding **Java implementation in SPMF** using:

- the same input datasets,
- the same parameter settings,
- and the same experimental conditions.

The returned pattern sets and associated values, such as support or utility, are compared to ensure matching outputs.

## Installation

### Install from PyPI

```bash
pip install pypatternminer
```

### Install from source

Clone the repository and install the package locally:

```bash
git clone https://github.com/taiduydinh/pypatternminer.git
cd pypatternminer
pip install .
```

If you want to install in editable mode for development:

```bash
pip install -e .
```

## Quick Start

Algorithms are currently organized by module. A typical usage pattern is to import the algorithm class from its corresponding module.

### Example: Apriori

```python
from pypatternminer.apriori import AlgoApriori

algo = AlgoApriori()
algo.runAlgorithm(
    minsup=0.5,
    input_path="contextPasquier99.txt",
    output_path="output_py.txt"
)
```

### Example: LCIM

```python
from pypatternminer.lcim import AlgoLCIM

algo = AlgoLCIM()
algo.runAlgorithm(
    input_file="DB_cost.txt",
    output_file="output_py.txt",
    minUtility=28.0,
    maxcost=10.0,
    minsupp=0.3
)
```

## Package Organization

The project is organized as follows:

```text
pypatternminer/
├── .github/                 # GitHub Actions workflows
├── datasets/                # testing datasets
├── pypatternminer/          # source code
│   ├── __init__.py
│   ├── apriori.py
│   ├── aprioriclose.py
│   ├── aprioriinverse.py
│   ├── ...
│   └── lcim.py
├── README.md
└── pyproject.toml
```

## Repository Structure

The repository is designed to support both algorithm development and reproducible experimentation:

- `pypatternminer/` contains the Python implementations of the algorithms;
- `datasets/` contains testing datasets used for validation and experiments;
- `.github/workflows/` contains the release and publishing workflows.

## Usage Notes

- Algorithms are currently accessed through their corresponding modules, for example:
  - `from pypatternminer.apriori import AlgoApriori`
  - `from pypatternminer.lcim import AlgoLCIM`
- Input files, parameters, and output formats may differ across algorithms depending on their original design and reference implementation.

## Contributing

Contributions are welcome.

You can contribute by:

- implementing additional pattern-mining algorithms;
- improving documentation and examples;
- reporting bugs or testing issues;
- adding benchmark datasets and validation cases;
- improving code quality and reproducibility.

If you would like to contribute, please open an issue or submit a pull request.

## Citation

If you use **pypatternminer** in your research, please cite the repository or the related paper if available.

A formal citation entry can be added here in future releases.

## License

pypatternminer is released under the **GNU General Public License v3.0 (GPLv3)**.

- Full license text: [LICENSE](LICENSE)
- GNU GPL v3: https://www.gnu.org/licenses/gpl-3.0.en.html

**pypatternminer** is intended to serve as both a practical software library and a research infrastructure for the pattern-mining community. By combining algorithmic breadth, reproducibility, and public accessibility, the project aims to support researchers, educators, and practitioners working on pattern mining and related areas.

At the current stage, several implementations were developed by adapting ideas and code structure from the original **SPMF** Java library, followed by validation to ensure that the Python versions produce results consistent with the corresponding reference implementations under the same datasets and parameter settings.

The project may also include original extensions, refactoring, interface changes, and future optimizations beyond the original Java implementation. However, where code is derived from SPMF, the project follows the requirements of the **GNU GPL v3** license.
