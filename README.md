# MELT

MELT main file is under src/inference/main.py. The main file takes the following arguments:


To run the script, you need to provide the following input arguments:

1. `--library`: The name of the library in the format "user/repo" (e.g., "scikit-learn/scikit-learn").
2. `--pr`: The Pull Request (PR) number.
3. `--out_dir` (optional): The output directory where the generated rules will be saved. The default is the current directory.
4. `--version` (optional): The version of the library (e.g., 1.5). The default is "1.5".

The script will then mine the changes from the specified PR, filter deprecated APIs, and generate comby rules based on the changes. The generated rules will be saved as JSON files in the specified output directory.

Please make sure to provide the required arguments when running the script, and ensure that your GitHub API keys are correctly set up.

## Comments
This script is designed to infer comby rules for Python code from unidiffs in a given GitHub repository. It mines and generalizes Abstract Syntax Trees (AST) from changes in the code to generate rules for code modification. Before running the script, make sure you have provided your GitHub API keys in the appropriate configuration file or environment variable, as the script requires access to the GitHub API.


## Disclaimer
This is a research prototype. If you have any problems setting an environment for MELT to work feel free to reach out or open an issue

### Set up your environment:

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
Set up GitHub API keys:
Before running the script, ensure you've set up your GitHub API keys. They can be added to the appropriate configuration file or set as an environment variable. The script requires access to the GitHub API for mining changes.
