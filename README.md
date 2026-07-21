# Red Team Foundry Local Models

This project downloads and runs a language model on the local machine with Foundry Local, then evaluates it with the Azure AI Evaluation red-team SDK. It also includes an interactive chat utility for inspecting a model before a scan.

Azure Developer CLI (`azd`) provisions the Microsoft Foundry account and project required by the evaluator. The model under test is not deployed to Azure.

The target model and its inference run on the local machine. Azure AI Evaluation uses the configured Microsoft Foundry project to generate attacks and score responses across these risk categories:

- Violence
- Hate and unfairness
- Sexual content
- Self-harm

The scan applies baseline, grouped easy and moderate, encoding, and text-transformation attack strategies. It reports the Attack Success Rate (ASR), where a higher value means more adversarial prompts elicited responses above the configured safety threshold.

## Execution Model

This is a hybrid local and cloud workflow, not a fully offline red-team scanner:

- **Local:** The target model is downloaded, loaded, and queried through Foundry Local. The Python scan process, callback, caches, logs, and generated artifacts are also local.
- **Azure:** The Azure AI Evaluation SDK uses the configured Microsoft Foundry project to generate adversarial attacks and score the model responses. This requires an Azure connection, `AZURE_AI_PROJECT_ENDPOINT`, Azure CLI credentials, and provisioned Foundry resources.

In short, the model inference happens locally, while attack generation and safety evaluation depend on Azure services.

For each attack, the evaluator generates a prompt through the configured Foundry project, invokes the in-process callback, sends that prompt to the local model, and returns the model response for Azure-based scoring. Treat scan prompts and responses as data that crosses the Azure service boundary even though the model weights and inference runtime remain local. Model listing, cache management, and interactive chat do not use the Azure evaluator.

For more information, see [Run AI Red Teaming Agent Locally (Azure AI Evaluation SDK) - Microsoft Foundry | Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/run-scans-ai-red-teaming-agent).

## Scripts

### `redteam_foundry_local_model.py`

The main entry point. It can:

- List available or downloaded Foundry Local models.
- Delete a downloaded model from the local cache.
- Download and load a selected model.
- Run an Azure AI Evaluation red-team scan against it.
- Save detailed evidence, logs, and aggregate scorecards.
- Run sequentially or with limited parallelism.

### `foundry_local_interactive_chat.py`

An interactive smoke-test utility. It downloads and loads a selected model, keeps conversation history for the session, and unloads the model when the user exits. The red-team callback is intentionally single-turn, so this utility is useful for manual, stateful inspection before a scan.

### `foundry_local_model_utils.py`

An internal module shared by both command-line scripts. It owns Foundry Local catalog initialization, model lookup and display, downloads, cache detection, and cache deletion. It is not a standalone entry point.

### Infrastructure

- `azure.yaml`: Configures the Bicep deployment and post-provision hook.
- `infra/main.bicep`: Creates the resource group and invokes the Foundry module.
- `infra/modules/foundry.bicep`: Creates the Microsoft Foundry account and project.
- `scripts/write-env.sh`: Writes the provisioned project endpoint to `.env` without removing unrelated entries.

## Prerequisites

You need:

- Python 3.10 through 3.13 for the Azure AI Evaluation red-team dependencies.
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

## Getting Started

### 1. Clone the repository

Clone the project and enter its directory:

```bash
git clone https://github.com/mardianto-msft/foundry-local-eval.git
cd foundry-local-eval
```

### 2. Install the Python dependencies

From the repository root:

```bash
python3 -m venv .fl
source .fl/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Sign in to Azure

AZD provisions infrastructure, while the Python evaluator authenticates through `AzureCliCredential`. Sign in to both tools:

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

### 5. Verify the setup

Keep the virtual environment active and verify that the scripts and model catalog are available:

```bash
python redteam_foundry_local_model.py --help
python redteam_foundry_local_model.py --list-model
```

Model listing, cached-model listing, and cache deletion do not require Azure credentials. Running a red-team scan does.

## Model Management

List all models available through the Foundry Local catalog:

```bash
python redteam_foundry_local_model.py --list-model
```

List only models already downloaded to the project-local cache:

```bash
python redteam_foundry_local_model.py --list-cached-models
python redteam_foundry_local_model.py --list-downloaded-models
```

Delete a downloaded model from the local cache:

```bash
python redteam_foundry_local_model.py --delete-model qwen2.5-0.5b
```

Deletion uses the Foundry Local SDK's cache-removal operation. The script reports when the model is not downloaded and uses the same process lock as scans to avoid deleting a model while a scan is using it.

Downloaded models are stored under `.foundry-local/`. A model is downloaded automatically when either command-line script first needs it.

## Interactive Chat

Start a stateful chat session:

```bash
python foundry_local_interactive_chat.py --model qwen2.5-0.5b
```

Enter `exit` or `quit` to unload the model and stop. Empty prompts are ignored.

The chat utility can also inspect the catalog:

```bash
python foundry_local_interactive_chat.py --list-models
python foundry_local_interactive_chat.py --cached
python foundry_local_interactive_chat.py --downloaded
```

## Red-Team Scans

Run a sequential scan, which is the safer default for local CPU models:

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

The script permits only one scan or model-deletion operation at a time. It serializes calls to the shared local chat client even when parallel attack orchestration is enabled, because the local client is not used concurrently.

Each scan covers these risk categories:

- Violence
- Hate and unfairness
- Sexual content
- Self-harm

The configured strategies include grouped easy and moderate attacks, character spacing, ROT13, Unicode confusables, character swapping, Morse code, leetspeak, URL encoding, binary encoding, and a Base64-plus-ROT13 composition. The SDK also runs baseline prompts. Grouped strategies expand into individual techniques, so the number of model calls is substantially larger than `risk categories × objectives`.

### Scan Options

| Option | Default | Description |
|--------|---------|-------------|
| `--model MODEL` | `phi-4-mini` | Foundry Local model alias to download and scan. |
| `--num-objectives N` | `2` | Attack objectives generated for each risk category. Increasing this can greatly increase runtime. |
| `--max-tokens N` | `512` | Maximum tokens in each local model response. |
| `--temperature VALUE` | `0.0` | Sampling temperature used by the local chat client. |
| `--parallel` | Disabled | Allows parallel attack orchestration. Local inference remains serialized. |
| `--max-parallel-tasks N` | `1` | Maximum SDK tasks when `--parallel` is enabled. |
| `--scan-timeout SECONDS` | `7200` | Overall scan timeout. |
| `--output PATH` | `<model>-redteam-results.json` | SDK export path. See the output notes below. |

Use `python redteam_foundry_local_model.py --help` for the complete CLI reference.

## Results

Each run creates a hidden `.scan_<name>_<timestamp>/` evidence directory in the repository root. Start with:

- `scorecard.txt`: Quick human-readable summary.
- `<risk>_<strategy>_results.jsonl`: Detailed prompts, model responses, scores, and scoring rationales for each risk and strategy combination.
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

The evidence directory also contains:

- `results.json`: Evaluation-run status, counts, strategies, and usage summary.
- `instance_results.json`: Serialized result for the scan instance.
- `redteam_info.json`: Artifact index, completion status, and ASR by strategy and category.
- `redteam.log`: Detailed SDK execution log.

The SDK also writes to the path passed through `--output`. With the SDK version used by this project, the default path such as `qwen2.5-0.5b-redteam-results.json` is created as a directory despite its `.json` suffix. It contains:

- `evaluation_results.json`: The exported scorecard and detailed evaluation data.
- `results.json`: Evaluation metadata and status.

Both `.scan_*/` and `*-redteam-results.json` paths are excluded from Git by default.

## Local Data

The scripts keep generated state inside the project directory:

- `.foundry-local/`: Downloaded Foundry Local model data.
- `.azure/`: AZD environments and deployment state.
- `.pyrit-data/`: PyRIT state.
- `.cache/` and `.tmp/`: Runtime cache and temporary files.
- `.redteam_foundry_local_model.lock`: Process lock used by scans and model deletion.
- `.scan_*/`: Per-run evidence and scorecards.
- `*-redteam-results.json/`: SDK export directories for the current SDK behavior.

The red-team script unloads the model and releases its lock in a `finally` block, including when a scan fails. The interactive chat utility similarly unloads its model when the session ends.

To remove a downloaded model without deleting other project state, use `--delete-model`. To remove generated scan artifacts, delete the relevant `.scan_*/` and `*-redteam-results.json/` directories.

## Troubleshooting

### Missing project endpoint

If a scan reports `Set AZURE_AI_PROJECT_ENDPOINT before running this script`, run `azd up` or inspect the selected AZD environment:

```bash
azd env get-values
```

Confirm that the root `.env` contains `AZURE_AI_PROJECT_ENDPOINT`. The script loads this file with `python-dotenv`.

### Authentication failures

Refresh the Azure CLI session used by the evaluator:

```bash
az login
az account show --output table
```

Use `azd auth login --check-status` separately to verify the AZD session used for provisioning.

### Another run is active

Only one scan or model-deletion operation can hold the project lock. Stop the other process before retrying. Do not manually remove the lock file while a scan is active.

### Long scan times

Start with the defaults. Keep parallel execution disabled for CPU-only models, reduce `--num-objectives`, or lower `--max-tokens`. Increasing parallel SDK tasks does not make the shared local model client concurrent.

## Remove Azure Resources

To delete the resource group and all resources provisioned for the selected AZD environment:

```bash
azd down
```

Review the environment shown by AZD before confirming because this operation deletes the resource group, Foundry account, and Foundry project. It does not delete local models or scan artifacts.
