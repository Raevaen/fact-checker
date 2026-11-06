param managedClusters_otari_hack_aks_name string = 'otari-hack-aks'

resource managedClusters_otari_hack_aks_name_resource 'Microsoft.ContainerService/managedClusters@2026-05-02-preview' = {
  name: managedClusters_otari_hack_aks_name
  location: 'italynorth'
  sku: {
    name: 'Base'
    tier: 'Free'
  }
  kind: 'Base'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    kubernetesVersion: '1.36'
    dnsPrefix: 'otari-hack-rg-italy-480619'
    agentPoolProfiles: [
      {
        name: 'nodepool1'
        count: 1
        vmSize: 'standard_b2als_v2'
        osDiskSizeGB: 128
        osDiskType: 'Managed'
        kubeletDiskType: 'OS'
        maxPods: 250
        type: 'VirtualMachineScaleSets'
        enableAutoScaling: false
        scaleDownMode: 'Delete'
        powerState: {
          code: 'Running'
        }
        orchestratorVersion: '1.36'
        enableNodePublicIP: false
        mode: 'System'
        enableEncryptionAtHost: false
        enableUltraSSD: false
        osType: 'Linux'
        osSKU: 'Ubuntu'
        nodeImageVersion: 'AKSUbuntu-2404gen2containerd-202610.30.1'
        upgradeStrategy: 'Rolling'
        upgradeSettings: {
          maxSurge: '10%'
          maxUnavailable: '0'
        }
        enableFIPS: false
        securityProfile: {
          sshAccess: 'LocalUser'
          enableVTPM: false
          enableSecureBoot: false
        }
      }
    ]
    linuxProfile: {
      adminUsername: 'azureuser'
      ssh: {
        publicKeys: [
          {
            keyData: 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCQbp1WoJ8YS2NbVoqF5NAoB9m4QQUkCxO+xAUcyKgc5eSx9s1JuzC7Q/ynFlQs0UdgmiCAs2PTbU1s0OZbz1slCNnengsIvbOGF93DIny4MQvt0WsnVGNbnMEPaTf+xcKCpWwgFuU1m1ZMZhN4onPn2an3iT5LY4dm3fGIQhrLFO17UX2b9OL4pb+D7SIgjj5PzJuJ4C4GVBIVca2ZYOaOxCKk6RxH6NJhlN88xJugQXgxD4DxNEfqMeWvbtDO9d3uwH5XPi66G32akgQN0XliT/d5+KXnZj9FB5wVW68s4Zr1LSeTfs7TR0YZowqCqLgkpVSk402/svtT+jE8++Cp'
          }
        ]
      }
    }
    servicePrincipalProfile: {
      clientId: 'msi'
    }
    nodeResourceGroup: 'MC_rg-italy_${managedClusters_otari_hack_aks_name}_italynorth'
    enableRBAC: true
    supportPlan: 'KubernetesOfficial'
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      networkPolicy: 'none'
      networkDataplane: 'azure'
      loadBalancerSku: 'standard'
      loadBalancerProfile: {
        managedOutboundIPs: {
          count: 1
        }
        backendPoolType: 'nodeIPConfiguration'
      }
      podCidr: '10.244.0.0/16'
      serviceCidr: '10.0.0.0/16'
      dnsServiceIP: '10.0.0.10'
      outboundType: 'loadBalancer'
      podCidrs: [
        '10.244.0.0/16'
      ]
      serviceCidrs: [
        '10.0.0.0/16'
      ]
      ipFamilies: [
        'IPv4'
      ]
      podLinkLocalAccess: 'IMDS'
    }
    identityProfile: {
      kubeletidentity: {}
    }
    autoUpgradeProfile: {
      nodeOSUpgradeChannel: 'NodeImage'
    }
    disableLocalAccounts: false
    securityProfile: {}
    storageProfile: {
      diskCSIDriver: {
        enabled: true
      }
      fileCSIDriver: {
        enabled: true
      }
      snapshotController: {
        enabled: true
      }
    }
    oidcIssuerProfile: {
      enabled: true
    }
    nodeDisruptionProfile: {
      nodeDisruptionPolicy: 'Allow'
    }
    workloadAutoScalerProfile: {}
    metricsProfile: {
      costAnalysis: {
        enabled: false
      }
    }
    nodeProvisioningProfile: {
      mode: 'Manual'
    }
    bootstrapProfile: {
      artifactSource: 'Direct'
    }
    hostedSystemProfile: {
      enabled: false
    }
    enableFIPS: false
    healthMonitorProfile: {
      enableContinuousControlPlaneAndAddonMonitor: false
      enableOnDemandMonitor: false
    }
  }
}

resource managedClusters_otari_hack_aks_name_nodepool1 'Microsoft.ContainerService/managedClusters/agentPools@2026-05-02-preview' = {
  parent: managedClusters_otari_hack_aks_name_resource
  name: 'nodepool1'
  properties: {
    count: 1
    vmSize: 'standard_b2als_v2'
    osDiskSizeGB: 128
    osDiskType: 'Managed'
    kubeletDiskType: 'OS'
    maxPods: 250
    type: 'VirtualMachineScaleSets'
    enableAutoScaling: false
    scaleDownMode: 'Delete'
    powerState: {
      code: 'Running'
    }
    orchestratorVersion: '1.36'
    enableNodePublicIP: false
    mode: 'System'
    enableEncryptionAtHost: false
    enableUltraSSD: false
    osType: 'Linux'
    osSKU: 'Ubuntu'
    nodeImageVersion: 'AKSUbuntu-2404gen2containerd-202610.30.1'
    upgradeStrategy: 'Rolling'
    upgradeSettings: {
      maxSurge: '10%'
      maxUnavailable: '0'
    }
    enableFIPS: false
    securityProfile: {
      sshAccess: 'LocalUser'
      enableVTPM: false
      enableSecureBoot: false
    }
  }
}

resource managedClusters_otari_hack_aks_name_nodepool1_aks_nodepool1_11765520_vmss000000 'Microsoft.ContainerService/managedClusters/agentPools/machines@2026-05-02-preview' = {
  parent: managedClusters_otari_hack_aks_name_nodepool1
  name: 'aks-nodepool1-11765520-vmss000000'
  properties: {
    network: {}
  }
  dependsOn: [
    managedClusters_otari_hack_aks_name_resource
  ]
}
