{{/*
Set a consistent name for the app.
*/}}
{{- define "tails-server.app-name" -}}
{{- .Values.app.name }}{{ .Values.deploy.name.suffix }}
{{- end }}

{{/*
Set a consistent name for resources deployed by this chart.
*/}}
{{- define "tails-server.deploy-name" -}}
{{- .Values.deploy.name.prefix }}{{ .Values.deploy.name.suffix }}
{{- end }}

{{/*
Set the name of the service created by this chart.
*/}}
{{- define "tails-server.service-name" -}}
{{- $defaultSvcName := include "tails-server.deploy-name" . -}}
{{- default $defaultSvcName .Values.service.nameOverride }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "tails-server.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Combine the image name and tag into a single, consistent string.
*/}}
{{- define "tails-server.image" -}}
{{- .Values.deploy.image.name }}:{{ .Values.deploy.image.tag }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "tails-server.labels" -}}
helm.sh/chart: {{ include "tails-server.chart" . }}
{{ include "tails-server.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: {{ include "tails-server.app-name" . }}
app.kubernetes.io/role: {{ .Values.app.role }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- end }}

{{/*
Common labels plus default "name"
*/}}
{{- define "tails-server.labelsWithName" -}}
{{- include "tails-server.labels" . }}
name: {{ include "tails-server.deploy-name" . }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "tails-server.selectorLabels" -}}
app.kubernetes.io/env: {{ .Values.app.env }}
app.kubernetes.io/group: {{ .Values.app.group }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/name: {{ include "tails-server.app-name" . }}
{{- end }}
