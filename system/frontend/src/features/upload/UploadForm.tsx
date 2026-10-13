import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { LoaderCircle, Upload } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { uploadRun } from "@/api/audits"
import { getRules } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"

export function UploadForm({
  onCreated,
  initialRuleId,
}: {
  onCreated: (id: string) => void
  initialRuleId?: string
}) {
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState("")
  const [language, setLanguage] = useState("python")
  const [ruleIds, setRuleIds] = useState<string[]>([])
  const rules = useQuery({
    queryKey: ["published-rules", language],
    queryFn: () => getRules(language, true),
  })
  useEffect(() => {
    if (
      initialRuleId &&
      rules.data?.some(
        (rule) =>
          rule.id === initialRuleId &&
          rule.status === "published" &&
          rule.language === language,
      )
    )
      setRuleIds([initialRuleId])
  }, [initialRuleId, rules.data, language])
  const input = useRef<HTMLInputElement>(null)
  const cache = useQueryClient()
  const mutation = useMutation({
    mutationFn: () => uploadRun(file!, name, language, ruleIds),
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
      {mutation.error ? (
        <p role="alert">
          上传失败：{mutation.error.message}，已保留所选文件和输入。
        </p>
      ) : null}
      {initialRuleId &&
      rules.isSuccess &&
      !rules.data.some(
        (rule) => rule.id === initialRuleId && rule.status === "published",
      ) ? (
        <p role="status">
          携带的规则不属于当前语言或尚未发布，请切换语言或重新选择。
        </p>
      ) : null}
      <FieldGroup>
        <p className="text-sm text-muted-foreground">
          上传后并发运行 CodeQL 标准扫描与 Agent 独立粗筛，随后在 AI
          阶段统一复核。粗筛受预算限制，未检查范围会保留。
        </p>
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
              onValueChange={(value) => {
                setLanguage(value)
                setRuleIds([])
              }}
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
        <details open>
          <summary>补充已发布规则（最多 4 个版本）</summary>
          {rules.isPending ? (
            <p role="status" className="text-sm text-muted-foreground">
              正在读取已发布规则…
            </p>
          ) : rules.error ? (
            <p role="alert">读取已发布规则失败：{rules.error.message}</p>
          ) : rules.data?.length ? (
            rules.data.map((rule) => (
              <label
                className="stage-check"
                key={rule.id}
                htmlFor={`upload-rule-${rule.id}`}
              >
                <Checkbox
                  id={`upload-rule-${rule.id}`}
                  checked={ruleIds.includes(rule.id)}
                  disabled={!ruleIds.includes(rule.id) && ruleIds.length >= 4}
                  onCheckedChange={(checked) =>
                    setRuleIds(
                      checked
                        ? [...ruleIds, rule.id]
                        : ruleIds.filter((id) => id !== rule.id),
                    )
                  }
                />
                {rule.title} · {rule.id.slice(0, 8)}
              </label>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">
              当前语言暂无已发布的补充规则，不影响内置 CodeQL 扫描和 AI
              初审。规则生成、验收并发布后，可在这里选择。
            </p>
          )}
        </details>
      </FieldGroup>
    </form>
  )
}
