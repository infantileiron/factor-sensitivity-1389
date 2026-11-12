-- Incremental migration for archived-report correction workflow.
-- Target: existing MySQL 8.4 production database initialized from 001_schema.sql.
-- New databases are created directly from SQLAlchemy metadata (including these columns).
-- Run once inside a transaction window after stopping the backend/worker; safe on 8.4.11.

-- 1. Version chain on reports: old reports keep their immutable snapshot/CSV and become version 1.
ALTER TABLE reports
  ADD COLUMN version INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN root_id VARCHAR(36) NULL,
  ADD COLUMN predecessor_id VARCHAR(36) NULL,
  ADD CONSTRAINT fk_reports_root FOREIGN KEY (root_id) REFERENCES reports(id),
  ADD CONSTRAINT fk_reports_predecessor FOREIGN KEY (predecessor_id) REFERENCES reports(id);

-- One report can have at most one successor; this also blocks concurrent duplicate approvals.
CREATE UNIQUE INDEX uq_reports_predecessor_id ON reports(predecessor_id);

UPDATE reports SET root_id = id WHERE root_id IS NULL;

-- 2. Correction requests (replacement-run applications).
CREATE TABLE correction_requests (
  id VARCHAR(36) NOT NULL PRIMARY KEY,
  created_at DATETIME NOT NULL,
  report_id VARCHAR(36) NOT NULL,
  replacement_run_id VARCHAR(36) NOT NULL,
  reason TEXT NOT NULL,
  state VARCHAR(20) NOT NULL DEFAULT 'submitted',
  requester VARCHAR(180) NOT NULL DEFAULT '',
  reviewer VARCHAR(180) NOT NULL DEFAULT '',
  review_note TEXT NOT NULL,
  successor_report_id VARCHAR(36) NULL,
  CONSTRAINT fk_correction_report FOREIGN KEY (report_id) REFERENCES reports(id),
  CONSTRAINT fk_correction_run FOREIGN KEY (replacement_run_id) REFERENCES runs(id),
  CONSTRAINT fk_correction_successor FOREIGN KEY (successor_report_id) REFERENCES reports(id)
);

CREATE INDEX ix_correction_requests_report_id ON correction_requests(report_id);
CREATE INDEX ix_correction_requests_state ON correction_requests(state);
