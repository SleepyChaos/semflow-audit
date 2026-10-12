import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { importKnowledge } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
export function KnowledgePanel({
  language,
  embeddingReady,
  embedded = false,
}: {
  language: string
  embeddingReady: boolean
  embedded?: boolean
}) {
  const [title, setTitle] = useState(""),
    [source, setSource] = useState(""),
    [content, setContent] = useState(""),
    [apiVersion, setApiVersion] = useState(""),
    [license, setLicense] = useState(""),
    [corpus, setCorpus] = useState("reference")
  const cache = useQueryClient()
  const add = useMutation({
    mutationFn: () =>
      importKnowledge({
        title,
        source,
        content,
        language,
        corpus,
        provenance: {
          api_version: apiVersion || "unknown",
          license: license || "unspecified",
          trust: "user_supplied",
        },
      }),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ["knowledge"] })
      setContent("")
      toast.success("知识已分块保存，可用于 BM25 检索")
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const form = (
    <div className="stage-form">
      <p className="page-note">
        资料用于真实检索。来源网址仅为引用，请粘贴完整正文。
        {!embeddingReady && "向量模型尚未配置，仍可保存并使用 BM25。"}
      </p>
      <div className="form-columns">
        <label htmlFor="knowledge-corpus">
          材料分类
          <select
            id="knowledge-corpus"
            className="native-select"
            value={corpus}
            onChange={(e) => setCorpus(e.target.value)}
          >
            <option value="reference">参考知识与 API 文档</option>
            <option value="rule_example">完整规则范例</option>
          </select>
        </label>
        <label htmlFor="knowledge-api-version">
          CodeQL语言库版本（规则生成按此过滤）
          <Input
            id="knowledge-api-version"
            value={apiVersion}
            onChange={(e) => setApiVersion(e.target.value)}
            placeholder="例如 4.0.10"
          />
        </label>
      </div>
      <label htmlFor="knowledge-title">
        资料标题
        <Input
          id="knowledge-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
        />
      </label>
      <label htmlFor="knowledge-source">
        来源或文档引用
        <Input
          id="knowledge-source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          maxLength={500}
        />
      </label>
      <label htmlFor="knowledge-license">
        资料许可证
        <Input
          id="knowledge-license"
          value={license}
          onChange={(e) => setLicense(e.target.value)}
        />
      </label>
      <label>
        资料正文（不会自动访问来源网址）
        <textarea
          className="audit-textarea knowledge-content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          maxLength={100000}
        />
      </label>
      {add.error && (
        <p role="alert">保存失败：{add.error.message}，输入已保留。</p>
      )}
      <Button
        disabled={
          !title.trim() ||
          !source.trim() ||
          content.trim().length < 30 ||
          add.isPending
        }
        onClick={() => add.mutate()}
      >
        {add.isPending ? "正在保存…" : "保存知识"}
      </Button>
      <p className="page-note">
        正文至少 30 个字符。CodeQL
        语言库版本用于匹配；保存后展示的版本是正文哈希。
      </p>
    </div>
  )
  return embedded ? (
    <section className="form-section">{form}</section>
  ) : (
    <details className="knowledge-panel">
      <summary>导入知识与版本</summary>
      {form}
    </details>
  )
}
