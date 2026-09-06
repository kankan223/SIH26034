import { useState } from 'react'
import { LedgerRow } from '../components/LedgerRow'
import { ComplianceStatusBadge } from '../components/ComplianceStatusBadge'
import {
  useRules,
  useRuleDetail,
  useCreateRule,
  useAddRuleVersion,
} from '../hooks/useRules'
import type { RuleCreateRequest, RuleVersionCreateRequest } from '../hooks/useRules'
import { getApiErrorMessage } from '../api/client'

export function RuleManagementPage() {
  const { data: list, isLoading: listLoading } = useRules()
  const { data: detail } = useRuleDetail(undefined)
  const createRule = useCreateRule()
  const addVersion = useAddRuleVersion()
  const [selectedRuleKey, setSelectedRuleKey] = useState<string | undefined>(undefined)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createForm, setCreateForm] = useState<RuleCreateRequest>({
    rule_key: '',
    title: '',
    description: '',
    product_categories: [],
    severity: 'major',
  })
  const [versionForm, setVersionForm] = useState<RuleVersionCreateRequest>({
    content: {},
    legal_reference: '',
    effective_date: new Date().toISOString().slice(0, 10),
  })
  const [expandedVersionId, setExpandedVersionId] = useState<string | undefined>(undefined)

  const rules = list?.rules ?? []
  const ruleDetail = detail

  if (listLoading && rules.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 py-16 text-ink/50">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink/20 border-t-ink" />
        <p className="text-small">Loading rules…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-title font-semibold text-ink">Rule management</h1>
          <p className="mt-1 text-small text-ink/60">
            {rules.length} rule{rules.length !== 1 ? 's' : ''} · admin only
          </p>
        </div>
        <button
          type="button"
          className="rounded-control bg-ink text-white px-4 py-2 text-label font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
          onClick={() => setShowCreateForm(true)}
        >
          New rule
        </button>
      </div>

      {/* New rule form — inline panel */}
      {showCreateForm ? (
        <section className="flex flex-col gap-3 border border-ink/10 rounded-surface bg-paper-deep p-4">
          <h2 className="text-label font-medium text-ink">New rule</h2>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-micro text-ink/50">Rule key *</span>
              <input
                type="text"
                className="rounded-control border border-ink/20 bg-white px-3 py-2 text-body text-ink placeholder:text-ink/40 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                value={createForm.rule_key}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, rule_key: e.target.value }))
                }
                placeholder="e.g. mrp_format"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-micro text-ink/50">Title *</span>
              <input
                type="text"
                className="rounded-control border border-ink/20 bg-white px-3 py-2 text-body text-ink placeholder:text-ink/40 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                value={createForm.title}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, title: e.target.value }))
                }
                placeholder="e.g. MRP format"
              />
            </label>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-micro text-ink/50">Description</span>
            <input
              type="text"
              className="rounded-control border border-ink/20 bg-white px-3 py-2 text-body text-ink placeholder:text-ink/40 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
              value={createForm.description}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, description: e.target.value }))
              }
              placeholder="Optional longer description"
            />
          </div>
          <div className="flex gap-2">
            <select
              className="rounded-control border border-ink/20 bg-white px-3 py-2 text-body text-ink focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
              value={createForm.severity}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, severity: e.target.value }))
              }
            >
              <option value="critical">Critical</option>
              <option value="major">Major</option>
              <option value="minor">Minor</option>
            </select>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="rounded-control border border-ink bg-transparent px-3 py-1.5 text-label text-ink hover:bg-paper-deep active:bg-paper-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
              >
                Cancel
              </button>
              <button
                disabled={!createForm.rule_key || !createForm.title || createRule.isPending}
                onClick={() => {
                  createRule.mutate(createForm, {
                    onSuccess: () => {
                      setShowCreateForm(false)
                      setCreateForm({ rule_key: '', title: '', description: '', product_categories: [], severity: 'major' })
                      setSelectedRuleKey(undefined)
                    },
                  })
                }}
                className="rounded-control bg-ink text-white px-3 py-1.5 text-label font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
              >
                {createRule.isPending ? 'Creating…' : 'Save rule'}
              </button>
            </div>
          </div>
          {createRule.error && (
            <p className="text-micro text-redline">{getApiErrorMessage(createRule.error)}</p>
          )}
        </section>
      ) : null}

      {/* Rule list — ledger rows per §3.2 */}
      <div className="flex flex-col border-t border-ink/10">
        {rules.map((rule) => {
          const severityStatus = rule.severity === 'critical'
            ? ('violation' as const)
            : rule.severity === 'major'
              ? ('needs-review' as const)
              : ('compliant' as const)
          return (
            <div key={rule.id}>
              <LedgerRow
                status={severityStatus}
                onClick={() => setSelectedRuleKey(rule.id)}
                className="cursor-pointer border-b border-ink/10"
              >
                <span className="flex items-center gap-3">
                  <span className="font-mono text-micro text-ink/50">{rule.rule_key}</span>
                  <span className="text-body text-ink">{rule.title}</span>
                </span>
                <div className="flex items-center gap-2 text-right">
                  <ComplianceStatusBadge status={severityStatus} />
                  <span className="text-micro text-ink/50">v{rule.version}</span>
                  <span className="text-micro text-ink/50">{rule.effective_date}</span>
                </div>
              </LedgerRow>

              {/* Expanded rule detail + version history */}
              {selectedRuleKey === rule.id && (
                <div className="mx-4 mb-3 flex flex-col gap-3 rounded-surface border border-ink/10 bg-paper-deep p-4">
                  {/* Detail */}
                  <div className="flex flex-col gap-1">
                    <h3 className="text-label font-medium text-ink">{rule.title}</h3>
                    <p className="text-small text-ink/60">{rule.rule_key}</p>
                  </div>

                  {/* Version list */}
                  <div className="flex flex-col">
                    <p className="text-micro text-ink/50">Version history</p>
                    {ruleDetail && ruleDetail.versions?.length === 0 ? (
                      <p className="text-small text-ink/50">No versions yet.</p>
                    ) : ruleDetail && ruleDetail.versions ? (
                      ruleDetail.versions.map((v) => (
                        <div
                          key={v.id}
                          className="flex items-center justify-between border-b border-ink/10 py-2 last:border-0"
                        >
                          <span className="flex items-center gap-2 text-small">
                            <span className="font-mono text-micro text-ink/50">v{v.version}</span>
                            {v.is_published && (
                              <span className="rounded-control bg-verify/10 px-2 py-0.5 text-micro text-verify">
                                published
                              </span>
                            )}
                            {v.published_at && <span className="text-micro text-ink/50">{v.published_at}</span>}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-micro text-ink/50">{v.effective_date}</span>
                            {!v.is_published && v.id !== expandedVersionId && (
                              <button
                                type="button"
                                className="text-micro text-ink/60 underline underline-offset-2 hover:text-ink"
                                onClick={() => setExpandedVersionId(v.id)}
                              >
                                Add version
                              </button>
                            )}
                            {v.id === expandedVersionId && (
                              <div className="flex flex-col gap-2">
                                <input
                                  type="text"
                                  className="rounded-control border border-ink/20 bg-white px-3 py-2 text-small text-ink placeholder:text-ink/40 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                                  placeholder="Legal reference *"
                                  value={versionForm.legal_reference}
                                  onChange={(e) =>
                                    setVersionForm((prev) => ({ ...prev, legal_reference: e.target.value }))
                                  }
                                />
                                <input
                                  type="date"
                                  className="rounded-control border border-ink/20 bg-white px-3 py-2 text-small text-ink focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                                  value={versionForm.effective_date}
                                  onChange={(e) =>
                                    setVersionForm((prev) => ({ ...prev, effective_date: e.target.value }))
                                  }
                                />
                                <div className="flex gap-2">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setExpandedVersionId(undefined)
                                      setVersionForm({ content: {}, legal_reference: '', effective_date: new Date().toISOString().slice(0, 10) })
                                    }}
                                    className="rounded-control border border-ink bg-transparent px-3 py-1.5 text-label text-ink hover:bg-paper-deep active:bg-paper-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    disabled={!versionForm.legal_reference || addVersion.isPending}
                                    onClick={() => {
                                      addVersion.mutate(
                                        { ruleId: rule.id, body: versionForm },
                                        {
                                          onSuccess: () => {
                                            setExpandedVersionId(undefined)
                                            setVersionForm({ content: {}, legal_reference: '', effective_date: new Date().toISOString().slice(0, 10) })
                                            setSelectedRuleKey(rule.id)
                                          },
                                        },
                                      )
                                    }}
                                    className="rounded-control bg-ink text-white px-3 py-1.5 text-label font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
                                  >
                                    {addVersion.isPending ? 'Adding…' : 'Add version'}
                                  </button>
                                </div>
                                {addVersion.error && (
                                  <p className="text-micro text-redline">{getApiErrorMessage(addVersion.error)}</p>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    ) : null}
                  </div>

                  {/* Republish button (published versions only) */}
                  {ruleDetail && ruleDetail.versions?.length > 0 && (
                    <div className="flex flex-col gap-1">
                      <p className="text-micro text-ink/50">Published versions</p>
                      {ruleDetail.versions.map((v) => (
                        v.is_published && (
                          <div className="flex items-center gap-2">
                            <span className="text-micro font-medium text-verify">
                              v{v.version} · {v.effective_date}
                            </span>
                            <button
                              type="button"
                              className="text-micro text-ink/60 underline underline-offset-2 hover:text-ink"
                              onClick={() => setExpandedVersionId(v.id)}
                            >
                              Republish
                            </button>
                          </div>
                        )
                      ))}
                    </div>
                  )}
                  {expandedVersionId && (
                    <div className="flex flex-col gap-2">
                      <input
                        type="text"
                        className="rounded-control border border-ink/20 bg-white px-3 py-2 text-small text-ink placeholder:text-ink/40 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                        placeholder="Legal reference *"
                        value={versionForm.legal_reference}
                        onChange={(e) =>
                          setVersionForm((prev) => ({ ...prev, legal_reference: e.target.value }))
                        }
                      />
                      <input
                        type="date"
                        className="rounded-control border border-ink/20 bg-white px-3 py-2 text-small text-ink focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
                        value={versionForm.effective_date}
                        onChange={(e) =>
                          setVersionForm((prev) => ({ ...prev, effective_date: e.target.value }))
                        }
                      />
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setExpandedVersionId(undefined)
                            setVersionForm({ content: {}, legal_reference: '', effective_date: new Date().toISOString().slice(0, 10) })
                          }}
                          className="rounded-control border border-ink bg-transparent px-3 py-1.5 text-label text-ink hover:bg-paper-deep active:bg-paper-deep focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
                        >
                          Cancel
                        </button>
                        <button
                          disabled={!versionForm.legal_reference || addVersion.isPending}
                          onClick={() => {
                            addVersion.mutate(
                              { ruleId: rule.id, body: versionForm },
                              {
                                onSuccess: () => {
                                  setExpandedVersionId(undefined)
                                  setVersionForm({ content: {}, legal_reference: '', effective_date: new Date().toISOString().slice(0, 10) })
                                  setSelectedRuleKey(rule.id)
                                },
                              },
                            )
                          }}
                          className="rounded-control bg-ink text-white px-3 py-1.5 text-label font-medium transition-colors hover:bg-ink/90 active:bg-ink/80 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
                        >
                          {addVersion.isPending ? 'Adding…' : 'Add version'}
                        </button>
                      </div>
                      {addVersion.error && (
                        <p className="text-micro text-redline">{getApiErrorMessage(addVersion.error)}</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default RuleManagementPage
