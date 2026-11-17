import type { PendingGuardedOperation } from './guarded';

/** Which guarded surfaces App shows. A pending/unknown CSV_REPORT operation owns the report panel only: it must not show the
 *  stale workspace success status or the financial archive panel (which would describe a different operation). */
export interface GuardedSurfaces {
  workspaceStatusVisible: boolean;
  archive: { visible: boolean; pending: PendingGuardedOperation | null; retry: boolean };
  report: { visible: boolean; pending: PendingGuardedOperation | null; retry: boolean };
}

export function guardedSurfaces(pending: PendingGuardedOperation | null, archiveReference: unknown, reportReference: unknown): GuardedSurfaces {
  const reportPending = pending?.kind === 'CSV_REPORT';
  const financialPending = pending !== null && !reportPending;
  return {
    workspaceStatusVisible: !reportPending,
    archive: { visible: Boolean(archiveReference) || financialPending, pending: reportPending ? null : pending, retry: financialPending },
    report: { visible: Boolean(reportReference) || reportPending, pending: reportPending ? pending : null, retry: reportPending },
  };
}
