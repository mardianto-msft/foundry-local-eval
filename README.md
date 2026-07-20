# Foundry Local Red Team Evaluation

This project downloads and runs a language model locally with Foundry Local, then evaluates it with the Azure AI Evaluation red-team SDK. Azure Developer CLI (`azd`) provisions the Microsoft Foundry resources required for attack generation and scoring.

The target model and its inference run on the local machine. Azure AI Evaluation uses the configured Microsoft Foundry project to generate attacks and score responses across these risk categories:

- Violence
- Hate and unfairness
- Sexual content
- Self-harm

The scan applies baseline, easy, moderate, encoded, and text-transformation attack strategies and reports the Attack Success Rate (ASR). A higher ASR means more attacks produced responses above the configured safety threshold.

## Scripts

### `redteam_foundry_local_model.py`

The main entry point. It can:

- List available or downloaded Foundry Local models.
- Download and load a selected model.
- Run an Azure AI Evaluation red-team scan against it.
- Save detailed evidence, logs, and aggregate scorecards.
- Run sequentially or with limited parallelism.

### `test_foundry_local.py`

A small interactive smoke-test utility. It is intentionally retained because the main script does not provide stateful chat: this script keeps conversation history and lets you manually inspect a model before running a longer scan.

## Getting Started

### 1. Install the prerequisites

You need:

- Python 3.10 or later.
- A platform supported by [Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/get-started).
- An Azure subscription where you can create a resource group, Microsoft Foundry resource, and Foundry project.
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli).
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) 1.27 or later.

On Ubuntu or Debian, install the Azure CLIs with:

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
curl -fsSL https://aka.ms/install-azd.sh | bash
```

Verify the installations:

```bash
python3 --version
az version
azd version
```

Use the linked installation guides above for other operating systems.

### 2. Install the Python dependencies

From the repository root:

```bash
python3 -m venv .fl
source .fl/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Sign in to Azure

AZD provisions infrastructure, while the Python evaluator uses Azure CLI credentials. Sign in to both:

```bash
azd auth login
az login
```

Verify both sessions:

```bash
azd auth login --check-status
az account show --output table
```

### 4. Provision Microsoft Foundry

Provision the Azure resources:

```bash
azd up
```

On the first run, AZD prompts for the Azure subscription, environment name, and region. The infrastructure defaults to `eastus2`. The environment name determines every resource name:

| Resource | Name |
|----------|------|
| Resource group | `rg-<environment-name>` |
| Microsoft Foundry resource | `aif-<environment-name>` |
| Foundry project | `proj-<environment-name>` |

For example, the `dev` environment creates `rg-dev`, `aif-dev`, and `proj-dev`.

After provisioning, [scripts/write-env.sh](scripts/write-env.sh) automatically writes `AZURE_AI_PROJECT_ENDPOINT` to the root `.env` file. Existing unrelated entries are preserved, and `.env` is excluded from Git.

You can inspect all deployment outputs with:

```bash
azd env get-values
```

The resulting `.env` entry has this form:

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://aif-<environment-name>.services.ai.azure.com/api/projects/proj-<environment-name>
```

### 5. Run the evaluator

Keep the virtual environment active, then continue with one of the commands below.

## Usage

List models:

```bash
python redteam_foundry_local_model.py --list-model
python redteam_foundry_local_model.py --list-cached-models
```

Interactively test a model:

```bash
python test_foundry_local.py --model qwen2.5-0.5b
```

Run a scan sequentially, which is the safer default for CPU models:

```bash
python redteam_foundry_local_model.py --model qwen2.5-0.5b
```

Run with limited parallelism:

```bash
python redteam_foundry_local_model.py \
  --model qwen2.5-0.5b \
  --parallel \
  --max-parallel-tasks 2
```

Useful options include:

- `--num-objectives`: Attack objectives per risk category; default is `2`.
- `--max-tokens`: Maximum local-model response tokens; default is `512`.
- `--temperature`: Local-model sampling temperature; default is `0.0`.
- `--scan-timeout`: Overall timeout in seconds; default is `7200`.
- `--output`: Path for the exported result JSON.

Use `python redteam_foundry_local_model.py --help` for the complete CLI reference.

## Results

Each run creates a hidden `.scan_<name>_<timestamp>/` directory in the repository root. Start with:

- `scorecard.txt`: Quick human-readable summary.
- `*_results.jsonl`: Detailed prompts, model responses, scores, and scoring rationales for investigating individual attacks.
- `final_results.json`: Machine-readable aggregate scorecard.

For example, a Qwen 2.5 0.5B scan produced:

```text
Overall ASR: 10.71%
Attack Success: 12/112 attacks were successful

Risk Category    Baseline    Easy     Moderate
Violence         50.0%       8.33%    100.0%
Hate-unfairness  50.0%       8.33%     50.0%
Sexual            0.0%       0.0%       0.0%
Self-harm        50.0%       4.17%     50.0%
```

**ASR** means Attack Success Rate: the percentage of adversarial prompts that produced a response above the configured safety threshold. Lower is better. In this example, 12 of 112 attacks succeeded; moderate violence attacks were the weakest area, while no sexual-content attacks succeeded.

The directory also contains:

- `results.json`: Evaluation-run status, counts, strategies, and usage summary.
- `instance_results.json`: Serialized result for the scan instance.
- `redteam_info.json`: Artifact index, completion status, and ASR by strategy and category.
- `redteam.log`: Detailed SDK execution log.

The path passed through `--output`, or `<model>-redteam-results.json` by default, is also written by the SDK.

## Local Data

The scripts keep generated state inside the project directory:

- `.foundry-local/`: Downloaded Foundry Local model data.
- `.azure/`: AZD environments and deployment state.
- `.pyrit-data/`: PyRIT state.
- `.cache/` and `.tmp/`: Runtime cache and temporary files.

Only one red-team run can use this project at a time. The main script uses a lock file to prevent concurrent scans from conflicting over local model resources.

## Remove Azure Resources

To delete the resource group and all resources provisioned for the selected AZD environment:

```bash
azd down
```

Review the environment shown by AZD before confirming because this operation deletes the Foundry resource and project.
