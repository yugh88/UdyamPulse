{{- define "up.name" -}}{{ .Release.Name }}{{- end -}}

{{- define "up.labels" -}}
app.kubernetes.io/part-of: udyampulse
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* Pod template labels: the common set without the instance key, which the selector adds. */}}
{{- define "up.podLabels" -}}
app.kubernetes.io/part-of: udyampulse
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "up.selector" -}}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Hardened pod and container security, shared by every workload. */}}
{{- define "up.podSecurity" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "up.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{- define "up.appEnv" -}}
- name: UP_ENV
  value: {{ .Values.env | quote }}
- name: UP_DATA_REGION
  value: {{ .Values.dataRegion | quote }}
- name: POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
{{- range $k, $v := .Values.config }}
- name: {{ $k }}
  value: {{ $v | quote }}
{{- end }}
{{- end -}}
