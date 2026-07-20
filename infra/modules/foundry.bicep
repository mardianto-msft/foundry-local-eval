targetScope = 'resourceGroup'

@minLength(2)
@maxLength(64)
@description('The globally unique Microsoft Foundry account name.')
param accountName string

@description('The Azure region for the Microsoft Foundry resources.')
param location string = resourceGroup().location

@minLength(2)
@maxLength(64)
@description('The Microsoft Foundry project name.')
param projectName string

@description('Tags applied to the Microsoft Foundry resources.')
param tags object = {}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: accountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: projectName
    description: 'Security evaluation of Foundry Local models'
  }
  tags: tags
}

output accountName string = account.name
output projectName string = project.name
output projectEndpoint string = 'https://${account.name}.services.ai.azure.com/api/projects/${project.name}'
