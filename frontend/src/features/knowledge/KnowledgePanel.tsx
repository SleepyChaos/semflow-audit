import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { getKnowledge, importKnowledge, indexKnowledge } from "@/api/stages"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
export function KnowledgePanel({
  language,
  embeddingReady,
}: {
  language: string
  embeddingReady: boolean
}) {
  const [title, setTitle] = useState(""),
    [source, setSource] = useState(""),
    [content, setContent] = useState("")
  const cache = useQueryClient()
  const documents = useQuery({
    queryKey: ["knowledge"],
    queryFn: getKnowledge,
    refetchInterval: 15000,
  })
  const add = useMutation({
    mutationFn: () => importKnowledge({ title, source, content, language }),
    onSuccess: async () => {
      await cache.invalidateQueries()
      setContent("")
      toast.success("知识已分块保存")
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const index = useMutation({
    mutationFn: indexKnowledge,
    onSuccess: () => toast.success("向量索引已排队"),
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <details className="knowledge-panel">
      <summary>知识库管理与版本</summary>
      <p>资料用于真实检索，不能单独确认缺陷。</p>
      <div className="stage-form">
        <label htmlFor="knowledge-title">
          资料标题
          <Input
            id="knowledge-title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={200}
          />
        </label>
        <label htmlFor="knowledge-source">
          来源或文档引用
          <Input
            id="knowledge-source"
            value={source}
            onChange={(event) => setSource(event.target.value)}
            maxLength={500}
          />
        </label>
        <label>
          资料正文（不会自动访问来源网址）
          <textarea
            className="audit-textarea"
            value={content}
            onChange={(event) => setContent(event.target.value)}
            maxLength={100000}
          />
        </label>
        <Button
          variant="outline"
          disabled={!title || !source || content.length < 30 || add.isPending}
          onClick={() => add.mutate()}
        >
          导入知识
        </Button>
      </div>
      {documents.error ? <p role="alert">{documents.error.message}</p> : null}
      {documents.data
        ?.filter((item) => [language, "any"].includes(item.language))
        .map((item) => (
          <article key={item.document_id} className="candidate-card">
            <h4>{item.title}</h4>
            <p>{item.source}</p>
            <p>
              版本 {item.version.slice(0, 16)} · {item.chunks} 片段 ·{" "}
              {item.indexed_chunks} 已向量化
            </p>
            {item.index_error ? <p role="alert">{item.index_error}</p> : null}
            {!item.shared ? (
              <Button
                size="sm"
                variant="outline"
                disabled={!embeddingReady || index.isPending}
                onClick={() => index.mutate(item.document_id)}
              >
                建立向量索引
              </Button>
            ) : null}
          </article>
        ))}
    </details>
  )
}
