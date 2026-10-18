{{- define "recipe-finder.name" -}}recipe-finder{{- end -}}

{{- define "recipe-finder.image" -}}
{{ .Values.image.repository }}:{{ required "image.tag must be set to the git commit tag (e.g. --set image.tag=<sha>)" .Values.image.tag }}
{{- end -}}

{{- define "recipe-finder.selectorLabels" -}}
app.kubernetes.io/name: {{ include "recipe-finder.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "recipe-finder.labels" -}}
{{ include "recipe-finder.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}
