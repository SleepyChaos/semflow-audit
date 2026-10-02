import { useRef, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { LoaderCircle, Upload } from "lucide-react"
import { toast } from "sonner"
import { uploadRun } from "@/api/audits"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"

export function UploadForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState("")
  const [language, setLanguage] = useState("python")
  const input = useRef<HTMLInputElement>(null)
  const cache = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => uploadRun(file!, name, language),
    onSuccess: async (run) => {
      await cache.invalidateQueries({ queryKey: ["audits"] })
      onCreated(run.id)
      setFile(null)
      setName("")
      toast.success("审计任务已创建")
    },
    onError: (error: Error) => toast.error(error.message),
  })
  function choose(value: File | undefined) {
    if (!value) return
    if (
      !value.name.toLowerCase().endsWith(".zip") ||
      value.size > 20 * 1024 * 1024
    ) {
      toast.error("请选择不超过 20 MB 的 ZIP 代码包")
      return
    }
    setFile(value)
  }
  return (
    <form
      className="upload-panel"
      onSubmit={(event) => {
        event.preventDefault()
        if (file) mutation.mutate()
      }}
    >
      <input
        ref={input}
        type="file"
        accept=".zip"
        className="sr-only"
        aria-label="选择代码包"
        onChange={(event) => {
          choose(event.target.files?.[0])
          event.target.value = ""
        }}
      />
      <button
        type="button"
        className="upload-drop"
        onClick={() => input.current?.click()}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault()
          choose(event.dataTransfer.files[0])
        }}
      >
        <Upload size={36} strokeWidth={1.7} />
        <strong>{file?.name ?? "上传代码包"}</strong>
        <span>
          {file
            ? `${(file.size / 1024).toFixed(1)} KB · 点击更换`
            : "ZIP · 最多 20 MB"}
        </span>
      </button>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="project-name">项目名称（可选）</FieldLabel>
          <Input
            id="project-name"
            placeholder="例如：my-project"
            maxLength={120}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <div className="upload-actions">
          <Field>
            <FieldLabel>编程语言</FieldLabel>
            <RadioGroup
              value={language}
              onValueChange={setLanguage}
              className="flex flex-wrap gap-6"
            >
              <div className="flex items-center gap-2">
                <RadioGroupItem id="python" value="python" />
                <Label htmlFor="python">Python</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem id="javascript" value="javascript" />
                <Label htmlFor="javascript">JavaScript / TypeScript</Label>
              </div>
            </RadioGroup>
          </Field>
          <Button
            type="submit"
            size="lg"
            disabled={!file || mutation.isPending}
          >
            {mutation.isPending ? (
              <LoaderCircle className="animate-spin" data-icon="inline-start" />
            ) : null}
            {mutation.isPending ? "上传中" : "开始审计"}
          </Button>
        </div>
      </FieldGroup>
    </form>
  )
}
