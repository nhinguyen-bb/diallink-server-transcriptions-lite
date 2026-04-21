{{/*
Expand the name of the chart.
*/}}
{{- define "diallink_transcriptions_lite.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "diallink_transcriptions_lite.fullname" -}}
{{- default "diallink-server-transcriptions" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "diallink_transcriptions_lite.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "diallink_transcriptions_lite.labels" -}}
helm.sh/chart: {{ include "diallink_transcriptions_lite.chart" . }}
app: {{ .Release.Name }}
{{ include "diallink_transcriptions_lite.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "diallink_transcriptions_lite.selectorLabels" -}}
app.kubernetes.io/name: {{ include "diallink_transcriptions_lite.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "diallink_transcriptions_lite.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "diallink_transcriptions_lite.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
