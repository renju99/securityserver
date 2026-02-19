APPROVAL_FLOWS = {
  "IT": {
    "SLA": {"approvers": ["IT Manager"], "signers": ["CTO"]},
    "PO": {"approvers": ["IT Manager", "Finance Manager"], "signers": ["CFO"]},
    "Capex": {"approvers": ["Procurement Manager", "IT Manager", "Finance Manager"], "signers": ["CEO"]},
    "NDA": {"approvers": ["Legal Team"], "signers": ["CTO"]},
  },
  "Facilities": {
    "SLA": {"approvers": ["Facility Manager"], "signers": ["Head of Ops"]},
    "PO": {"approvers": ["Facility Manager", "Finance Manager"], "signers": ["CFO"]},
    "NDA": {"approvers": ["Legal Team"], "signers": ["Head of Ops"]},
  },
  "HR": {
    "SLA": {"approvers": ["HR Manager"], "signers": ["CHRO"]},
    "PO": {"approvers": ["HR Manager", "Finance Manager"], "signers": ["CFO"]},
    "NDA": {"approvers": ["Legal Team"], "signers": ["CHRO"]},
  },
}
