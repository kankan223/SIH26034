import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { RuleManagementPage } from '../RuleManagementPage'
import {
  useRules,
  useRuleDetail,
  useCreateRule,
  useAddRuleVersion,
  usePublishRuleVersion,
} from '../../hooks/useRules'

// ── Mocks ──────────────────────────────────────────────────────────────────
vi.mock('../../hooks/useRules', () => ({
  useRules: vi.fn(() => rulesList),
  useRuleDetail: vi.fn(() => ruleDetail),
  useCreateRule: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  })),
  useAddRuleVersion: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  })),
  usePublishRuleVersion: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  })),
}))

// ── Shared mock data ───────────────────────────────────────────────────────
const rulesList = {
  data: {
    rules: [
      {
        id: 'RULE-001',
        rule_key: 'mrp_format',
        title: 'MRP format',
        version: 2,
        latest_version_id: 'RULEV-0062',
        effective_date: '2026-02-01',
        product_categories: ['Food & Beverage'],
        severity: 'major',
      },
      {
        id: 'RULE-002',
        rule_key: 'net_quantity_declaration',
        title: 'Net quantity declaration',
        version: 1,
        latest_version_id: 'RULEV-0018',
        effective_date: '2020-01-01',
        product_categories: ['All'],
        severity: 'critical',
      },
    ],
  },
  isLoading: false,
  error: null,
}

const ruleDetail = {
  data: {
    id: 'RULE-001',
    rule_key: 'mrp_format',
    title: 'MRP format',
    description: 'MRP must state inclusive of all taxes',
    versions: [
      {
        id: 'RULEV-0062',
        version: 2,
        content: { applies_when: { product_categories: ['Food & Beverage'] }, validation: { format: 'MRP .* inclusive of all taxes' }, severity: 'major' },
        legal_reference: 'Legal Metrology (Packaged Commodities) Rules 2011, Rule 6(1)(f)',
        effective_date: '2026-02-01',
        end_date: null,
        published_by: 'admin',
        published_at: '2026-02-01',
        is_published: true,
      },
      {
        id: 'RULEV-0061',
        version: 1,
        content: { applies_when: { product_categories: ['All'] }, validation: {}, severity: 'major' },
        legal_reference: 'Legal Metrology (Packaged Commodities) Rules 2011, Rule 6(1)(f)',
        effective_date: '2020-01-01',
        end_date: '2026-01-31',
        published_by: 'system',
        published_at: '2020-01-01',
        is_published: false,
      },
    ],
    current_version_id: 'RULEV-0062',
    current_effective_date: '2026-02-01',
  },
  isLoading: false,
  error: null,
}

// ── Tests ──────────────────────────────────────────────────────────────────
describe('RuleManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    const createRuleSpy = vi.fn()
    ;(useCreateRule as ReturnType<typeof vi.fn>).mockReturnValue({ mutate: createRuleSpy, isPending: false, error: null })
    const addVersionSpy = vi.fn()
    ;(useAddRuleVersion as ReturnType<typeof vi.fn>).mockReturnValue({ mutate: addVersionSpy, isPending: false, error: null })
    const publishSpy = vi.fn()
    ;(usePublishRuleVersion as ReturnType<typeof vi.fn>).mockReturnValue({ mutate: publishSpy, isPending: false, error: null })
  })

  it('renders the rule list with rule keys and titles', () => {
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    expect(screen.getByText('mrp_format')).toBeInTheDocument()
    expect(screen.getByText('Net quantity declaration')).toBeInTheDocument()
  })

  it('renders version numbers and effective dates in each row', () => {
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('2026-02-01')).toBeInTheDocument()
  })

  it('expands the rule detail panel when the row is clicked', async () => {
    const user = userEvent.setup()
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    await user.click(screen.getByText('mrp_format'))
    expect(screen.getByText('Version history')).toBeInTheDocument()
    expect(screen.getByText('published')).toBeInTheDocument()
  })

  it('renders the new-rule form controls', async () => {
    const user = userEvent.setup()
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: 'New rule' }))
    expect(screen.getByPlaceholderText('e.g. mrp_format')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('e.g. MRP format')).toBeInTheDocument()
  })

  it('creates a rule when the form is submitted', async () => {
    const user = userEvent.setup()
    const mutateSpy = vi.fn()
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    ;(useCreateRule as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mutateSpy,
      isPending: false,
      error: null,
    })
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: 'New rule' }))
    const ruleKeyInput = screen.getByPlaceholderText('e.g. mrp_format')
    const titleInput = screen.getByPlaceholderText('e.g. MRP format')
    await user.clear(ruleKeyInput)
    await user.type(ruleKeyInput, 'test_rule')
    await user.clear(titleInput)
    await user.type(titleInput, 'Test rule')
    await user.click(screen.getByRole('button', { name: 'Save rule' }))
    expect(mutateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ rule_key: 'test_rule', title: 'Test rule', description: '', severity: 'major' }),
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    )
  })

  it('opens the add-version form when Add version is clicked', async () => {
    const user = userEvent.setup()
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    await user.click(screen.getByText('mrp_format'))
    const addVersionButton = screen.getAllByRole('button', { name: 'Add version' })[0]
    await user.click(addVersionButton)
    expect(screen.getAllByPlaceholderText('Legal reference *')[0]).toBeInTheDocument()
  })

  it('submits a new version with the legal reference', async () => {
    const user = userEvent.setup()
    const mutateSpy = vi.fn()
    ;(useRules as ReturnType<typeof vi.fn>).mockReturnValue(rulesList)
    ;(useRuleDetail as ReturnType<typeof vi.fn>).mockReturnValue(ruleDetail)
    ;(useAddRuleVersion as ReturnType<typeof vi.fn>).mockReturnValue({
      mutate: mutateSpy,
      isPending: false,
      error: null,
    })
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    await user.click(screen.getByText('mrp_format'))
    const addVersionButtons = screen.getAllByRole('button', { name: 'Add version' })
    await user.click(addVersionButtons[0])
    const legalRefInput = screen.getAllByPlaceholderText('Legal reference *')[0]
    await user.type(legalRefInput, 'LMPC Rules 2011, Rule 6(1)(f)')
    const submitButton = screen.getAllByRole('button', { name: 'Add version' })[1]
    await user.click(submitButton)
    expect(mutateSpy).toHaveBeenCalled()
  })
})
