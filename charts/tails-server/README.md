# Tails Server Helm Chart

A simple, production‑ready Helm chart to deploy the Indy Tails Server.

- App: <https://github.com/bcgov/indy-tails-server>
- Kubernetes: >= 1.23 (uses autoscaling/v2)

## TL;DR

```bash
helm repo add tails-server https://bcgov.github.io/indy-tails-server
helm repo update
helm upgrade --install tails-server tails-server/tails-server \
  --namespace tails-server --create-namespace
```

## Prerequisites

- Kubernetes >= 1.23
- Metrics server (if enabling HPA)
- A default StorageClass (if enabling persistence without existingClaim)

## Configuration

Values below are the most commonly tuned. See `values.yaml` for the full list.

| Parameter | Default | Description |
|---|---|---|
| replicaCount | 1 | Desired replicas when HPA disabled |
| autoscaling.enabled | false | Enable HorizontalPodAutoscaler |
| autoscaling.minReplicas | 1 | HPA min replicas |
| autoscaling.maxReplicas | 4 | HPA max replicas |
| autoscaling.targetCPUUtilizationPercentage | 80 | HPA CPU target |
| image.repository | ghcr.io/bcgov/tails-server | Image repository |
| image.tag | chart appVersion | Image tag |
| service.type | ClusterIP | Service type |
| service.port | 6543 | Service port (TCP) |
| service.annotations | {} | Extra Service annotations |
| ingress.enabled | false | Create Ingress (OpenShift will auto‑create Route) |
| persistence.enabled | false | Enable persistent storage for tails files |
| persistence.existingClaim | "" | Use an existing PVC name |
| persistence.size | 5Gi | PVC size when creating new |
| persistence.accessModes | [ReadWriteOnce] | PVC access modes |
| persistence.storageClass | "" | StorageClass name |
| persistence.mountPath | /data | Container mount path for storage |
| server.host | 0.0.0.0 | Bind address inside the pod |
| server.port | "" | Override port (defaults to service.port) |
| server.logLevel | WARNING | Log level (e.g., INFO, WARNING, ERROR) |
| livenessProbe | see values.yaml | TCP liveness probe config |
| readinessProbe | see values.yaml | TCP readiness probe config |
| startupProbe | see values.yaml | TCP startup probe config |
| securityContext | {} | Container security context (see example below) |
| serviceAccount.create | true | Create a ServiceAccount |
| serviceAccount.automount | true | Automount SA token (set false to harden) |
| nodeSelector | {} | Node selector |
| tolerations | [] | Tolerations |
| affinity | {} | Affinity/anti‑affinity |
| pdb.enabled | false | Create PodDisruptionBudget when replicas > 1 |

### OpenShift notes

- Prefer using Ingress. OpenShift will create a Route automatically and may terminate TLS at the edge regardless of `ingress.tls` settings.
- For multi‑replica deployments, use RWX storage if your storage class supports it.

Example RWX values (OpenShift NetApp):

```yaml
persistence:
  enabled: true
  size: 10Gi
  accessModes:
    - ReadWriteMany
  storageClass: netapp-file-standard
  mountPath: /data
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 4
pdb:
  enabled: true
  minAvailable: 1
```

### Security hardening (example)

```yaml
securityContext:
  runAsNonRoot: true
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop: ["ALL"]
serviceAccount:
  automount: false
```

## License

Apache-2.0
