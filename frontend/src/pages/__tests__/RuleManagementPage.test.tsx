
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { RuleManagementPage } from '../RuleManagementPage'

const mockCreateRule = vi.fn()
const mockAddVersion = vi.fn()
const mockPublish = vi.fn()

vi.mock('../../hooks/useRules', () => ({
  useRules: vi.fn(() => ({
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
  })),
  useRuleDetail: vi.fn(() => ({
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
  })),
  useCreateRule: () => ({ mutate: mockCreateRule, isPending: false, error: null }),
  useAddRuleVersion: () => ({ mutate: mockAddVersion, isPending: false, error: null }),
  usePublishRuleVersion: () => ({ mutate: mockPublish, isPending: false, error: null }),
}))

describe('RuleManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCreateRule.mockClear()
    mockAddVersion.mockClear()
  })

  it('renders the rule list with rule keys and titles', () => {
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    expect(screen.getByText('mrp_format')).toBeInTheDocument()
    expect(screen.getByText('Net quantity declaration')).toBeInTheDocument()
  })

  it('renders version numbers and effective dates in each row', () => {
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)
    expect(screen.getByText('v2')).toBeInTheDocument()
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('2026-02-01')).toBeInTheDocument()
  })

  it('expands the rule detail panel when the row is clicked', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)

    await user.click(screen.getByText('mrp_format'))
    expect(screen.getByText('Version history')).toBeInTheDocument()
    expect(screen.getByText('published')).toBeInTheDocument()
  })

  it('renders the new-rule form controls', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /New rule/i }))
    expect(screen.getByPlaceholderText(/e.g. mrp_format/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/e.g. MRP format/i)).toBeInTheDocument()
  })

  it('creates a rule when the form is submitted', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: /New rule/i }))
    await user.type(screen.getByPlaceholderText(/e.g. mrp_format/i), 'test_rule')
    await user.type(screen.getByPlaceholderText(/e.g. MRP format/i), 'Test rule')
    await user.click(screen.getByRole('button', { name: /Save rule/i }))
    expect(mockCreateRule).toHaveBeenCalledWith(
      expect.objectContaining({ rule_key: 'test_rule', title: 'Test rule' }),
    )
  })

  it('opens the add-version form when Add version is clicked', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)

    await user.click(screen.getByText('mrp_format'))
    await user.click(screen.getByText('Add version (RULEV-0061)'))
    expect(screen.getByPlaceholderText(/Legal reference/i)).toBeInTheDocument()
  })

  it('submits a new version with the legal reference', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><RuleManagementPage /></MemoryRouter>)

    await user.click(screen.getByText('mrp_format'))
    await user.click(screen.getByText('Add version (RULEV-0061)'))
    expect(screen.getByPlaceholderText(/Legal reference/i)).toBeInTheDocument()

    await user.type(screen.getByPlaceholderText(/Legal reference/i), 'LMPC Rules 2011, Rule 6(1)(f)')
    await user.click(screen.getByRole('button', { name: /Add version/i }))
    expect(mockAddVersion).toHaveBeenCalled()
  })
})
