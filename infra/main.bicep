targetScope = 'subscription'

@minLength(1)
@maxLength(48)
@description('The AZD environment name used as the resource name suffix.')
param environmentName string

@description('The Azure region for all resources.')
param location string = 'eastus2'

var tags = {
  'azd-env-name': environmentName
}

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-07-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module foundryResources './modules/foundry.bicep' = {
  scope: resourceGroup
  params: {
    accountName: 'aif-${environmentName}'
    location: location
    projectName: 'proj-${environmentName}'
    tags: tags
  }
}

output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_AI_FOUNDRY_NAME string = foundryResources.outputs.accountName
output AZURE_AI_PROJECT_NAME string = foundryResources.outputs.projectName
output AZURE_AI_PROJECT_ENDPOINT string = foundryResources.outputs.projectEndpoint
