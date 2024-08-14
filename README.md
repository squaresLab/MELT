# MELT

The github action for MELT is found here: https://github.com/squaresLab/melt_action

## Set up your environment:

1. Create a python env.
```bash
python -m venv melt_env
source melt_env/bin/activate
```

2. Go to MELT's directory and install dependencies 

```bash
cd MELT
pip install -r requirements.txt
```

3. Add MELT to PYTHONPATH
```bash
export PYTHONPATH=$PYTHONPATH:`pwd`
```

## How to run

MELT main file is under src/inference/main.py. The main file takes the following arguments:

To run the script, you need to provide the following input arguments:

1. `--library`: The name of the library in the format "user/repo" (e.g., "scikit-learn/scikit-learn").
2. `--pr`: The Pull Request (PR) number.
3. `--gh_key`: A github access key (classic token) with only public permissions. This is used to extract data from the PR. Instructions on how to create a Token can be found [here](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic)
4. `api_keyword`: The name of the API being deprecated.
5. `--out_dir` (optional): The output directory where the generated rules will be saved. The default is the current directory.
6. `--version` (optional): The version of the library (e.g., 1.5). The default is "1.5".

The script will then mine the changes from the specified PR, filter deprecated APIs, and generate comby rules based on the changes. The generated rules will be saved as JSON files in the specified output directory.
Please make sure to provide the required arguments when running the script, and ensure that your GitHub API keys are correctly set up.

### Example:

```python
python3 src/inference/main.py --library pandas-dev/pandas --pr 44539 --gh_key ghp_********* --api_keyword append
```

Currently, it is necessary to provide the name of the deprecated API for which we want to mine rules. The zenodo versions contains the heuristics, including an NLP-based approach for identifying the relevant API names. 

## How to cite
```latex
@inproceedings{ramos2023melt,
  title={MELT: Mining Effective Lightweight Transformations from Pull Requests},
  author={Ramos, Daniel and Mitchell, Hailie and Lynce, In\\^es and Manquinho, Vasco and Martins, Ruben and Le Goues, Claire},
  booktitle={Proc. International Conference on Automated Software Engineering (ASE)},
  year={2023}
}
```

## Disclaimer
This is a research prototype. If you have any problems setting an environment for MELT to work feel free to reach out or open an issue.
