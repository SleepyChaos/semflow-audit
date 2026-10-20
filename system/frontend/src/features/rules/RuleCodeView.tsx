import { Check, Copy, Download } from "lucide-react"
import { useId, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"

export function RuleCodeView({
  query,
  modules,
}: {
  query: string
  modules: Record<string, string>
}) {
  const labelId = useId()
  const [filename, setFilename] = useState("query.ql")
  const [copied, copy] = useCopyToClipboard()
  const files: Record<string, string> = { "query.ql": query, ...modules }
  const name = filename in files ? filename : "query.ql"
  const content = files[name]
  function download() {
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/plain;charset=utf-8" }),
    )
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = name
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <section className="rule-code-view" aria-labelledby={labelId}>
      <header className="rule-code-toolbar">
        <div>
          <h4 id={labelId}>规则文本</h4>
          <span>CodeQL · {content.split("\n").length} 行</span>
        </div>
        <div className="rule-code-actions">
          <Button
            variant="outline"
            onClick={async () => {
              if (!(await copy(content)))
                toast.error("复制失败，请选择下方代码复制")
            }}
          >
            {copied === content ? <Check size={14} /> : <Copy size={14} />}
            {copied === content ? "已复制" : "复制代码"}
          </Button>
          <Button variant="outline" onClick={download}>
            <Download size={14} />
            下载文件
          </Button>
        </div>
      </header>
      {Object.keys(files).length > 1 ? (
        <WorkspaceSelect
          aria-label="规则代码文件"
          value={name}
          onValueChange={setFilename}
          options={Object.keys(files).map((value) => ({ value, label: value }))}
        />
      ) : (
        <p className="rule-code-filename">{name}</p>
      )}
      <textarea
        className="rule-code-content"
        aria-label={`${name} 完整规则代码`}
        value={content}
        readOnly
        spellCheck={false}
        wrap="off"
        rows={Math.min(Math.max(content.split("\n").length, 8), 18)}
      />
    </section>
  )
}
