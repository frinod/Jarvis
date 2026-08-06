# Azure Pipelines YAML skeleton

This is a basic Azure Pipelines YAML skeleton for building and deploying a .NET Core application.

## Prerequisites
* Azure DevOps project
* Azure subscription
* .NET Core SDK installed

## Usage
1. Create a new Azure Pipelines pipeline
2. Select 'Other Git' as the source
3. Select the repository containing this YAML file
4. Click 'Run'

## Variables
* `buildConfiguration`: The build configuration to use (e.g. 'Release')
* `your-resource-group`: The name of the Azure resource group
* `your-app-service`: The name of the Azure app service
