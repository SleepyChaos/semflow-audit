import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useId, useState } from "react"
import { toast } from "sonner"
import type { StageRun } from "@/api/stages"
import {
  generateVerificationSuite,
  getVerificationSuites,
  importVerificationSuite,
} from "@/api/verification"
import { Button } from "@/components/ui/button"
import { WorkspaceSelect } from "@/components/WorkspaceSelect"

export function VerificationSuitePanel({
  auditId,
  targets,
  suiteId,
  onSelect,
  modelReady,
  busy,
  stages,
}: {
  auditId: string
  targets: string[]
  suiteId: string
  onSelect: (id: string) => void
  modelReady: boolean
  busy: boolean
  stages: StageRun[]
}) {
  const selectionId = useId()
  const [image, setImage] = useState("")
  const [requirements, setRequirements] = useState("")
  const [importText, setImportText] = useState("")
  const [pendingId, setPendingId] = useState("")
  const cache = useQueryClient()
  const suites = useQuery({
    queryKey: ["verification-suites", auditId],
    queryFn: () => getVerificationSuites(auditId),
    refetchInterval: busy || pendingId ? 2000 : false,
  })
  const available = (suites.data ?? []).filter(
    (item) =>
      targets.length > 0 &&
      targets.every((id) => item.candidate_ids.includes(id)),
  )
  const pending = stages.find((item) => item.id === pendingId)
  const selected = available.find((item) => item.id === suiteId)
  useEffect(() => {
    if (pending && ["failed", "cancelled"].includes(pending.status)) {
      setPendingId("")
      return
    }
    if (pendingId && available.some((item) => item.id === pendingId)) {
      onSelect(pendingId)
      setPendingId("")
    }
  }, [available, pendingId, onSelect, pending])
  const generate = useMutation({
    mutationFn: () =>
      generateVerificationSuite(auditId, {
        candidate_ids: targets,
        image,
        requirements,
      }),
    onSuccess: async (result) => {
      setPendingId(result.id)
      await cache.invalidateQueries()
    },
    onError: (error: Error) => toast.error(error.message),
  })
  const imported = useMutation({
    mutationFn: () => importVerificationSuite(auditId, JSON.parse(importText)),
    onSuccess: async (result) => {
      setPendingId(result.id)
      setImportText("")
      await cache.invalidateQueries()
    },
    onError: (error: Error) => toast.error(error.message),
  })
  return (
    <section className="verification-suite-panel" aria-label="项目修复验收测试">
      <h4>1. 准备这个项目的验收测试</h4>
      <p className="page-note">
        测试会固定下来，对原始代码和补丁副本各运行两次。每个修复目标都需要安全测试，另需正常功能测试。AI
        生成的是待审阅草案。
      </p>
      <label>
        项目验证镜像（留空使用平台配置）
        <input
          className="audit-input"
          aria-label="项目验证镜像"
          value={image}
          onChange={(event) => setImage(event.target.value)}
          placeholder="包含项目依赖的已有 Docker 镜像"
        />
      </label>
      <label>
        需要保留的业务行为与测试要求
        <textarea
          className="audit-textarea"
          value={requirements}
          onChange={(event) => setRequirements(event.target.value)}
          placeholder="说明正常输入应该得到什么结果、权限和边界条件。缺少的信息会列为待核实。"
        />
      </label>
      <Button
        disabled={!modelReady || !targets.length || busy || generate.isPending}
        onClick={() => generate.mutate()}
      >
        AI 生成验收测试草案
      </Button>
      {generate.error && <p role="alert">{generate.error.message}</p>}
      <label htmlFor={selectionId}>
        选择已固定的项目测试集
        <WorkspaceSelect
          id={selectionId}
          className="native-select"
          aria-label="选择项目验收测试集"
          value={selected ? suiteId : ""}
          onValueChange={onSelect}
          options={[
            { value: "", label: "未选择；只能生成补丁草稿，不能确认修复" },
            ...available.map((item) => ({
              value: item.id,
              label: <>{item.suite.title}</>,
            })),
          ]}
        />
      </label>
      {suites.error && (
        <p role="alert">测试集读取失败：{suites.error.message}</p>
      )}
      {selected && (
        <div className="reader-explanation">
          <strong>{selected.suite.title}</strong>
          <p>{selected.suite.summary}</p>
          <ul>
            {selected.suite.cases.map((test) => (
              <li key={test.name}>
                <strong>
                  {test.category === "security" ? "安全" : "功能"}：
                </strong>
                {test.input_description} → {test.expected_behavior}
              </li>
            ))}
          </ul>
          {!!selected.suite.assumptions.length && (
            <>
              <h5>需要核实的测试前提</h5>
              <ul>
                {selected.suite.assumptions.map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
            </>
          )}
          <details>
            <summary>审阅测试代码与运行环境</summary>
            <p>
              镜像：{selected.image} · 测试指纹：
              {selected.suite_hash.slice(0, 16)}
            </p>
            {Object.entries(selected.suite.files).map(([name, code]) => (
              <div key={name}>
                <strong>{name}</strong>
                <pre className="source-code">{code}</pre>
              </div>
            ))}
          </details>
        </div>
      )}
      <details>
        <summary>导入团队已有测试集</summary>
        <p className="page-note">
          导入 JSON，包含 suite（测试文件、功能/安全用例和候选关联）以及
          image。导入后同样冻结，并执行前后对比。
        </p>
        <textarea
          className="audit-textarea"
          aria-label="测试集 JSON"
          value={importText}
          onChange={(event) => setImportText(event.target.value)}
        />
        <Button
          variant="outline"
          disabled={!importText.trim() || imported.isPending || busy}
          onClick={() => imported.mutate()}
        >
          导入测试集 JSON
        </Button>
        {imported.error && <p role="alert">{imported.error.message}</p>}
      </details>
    </section>
  )
}
