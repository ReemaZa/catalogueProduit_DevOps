{{- define "catalog.labels" -}}
app.kubernetes.io/part-of: catalog
app.kubernetes.io/managed-by: {{ .Release.Service }}
owner: {{ .Values.owner | quote }}
{{- end -}}
