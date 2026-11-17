import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { AccountApi } from './account';
import GuardedCsvReportPanel from './GuardedCsvReportPanel';
import { guardedSurfaces } from './guarded-pending';
import { guardedTranslations } from './guarded-i18n';
import i18n from './i18n';

// Fictional identifiers only.
const operation = '30000000-0000-4000-8000-000000000001';
const portfolio = '10000000-0000-4000-8000-000000000001';
const reportPending = { operationId: operation, portfolioId: portfolio, kind: 'CSV_REPORT' as const };
const financialPending = { operationId: operation, portfolioId: portfolio };

describe('App-level guarded surfaces while an operation is pending or unknown', () => {
  it('a pending CSV_REPORT hides the stale workspace status and the financial archive panel, and owns the report panel', () => {
    const surfaces = guardedSurfaces(reportPending, null, null);
    expect(surfaces.workspaceStatusVisible).toBe(false);
    expect(surfaces.archive).toEqual({ visible: false, pending: null, retry: false });
    expect(surfaces.report).toEqual({ visible: true, pending: reportPending, retry: true });
  });

  it('a pending CSV_REPORT still hides the financial archive panel when an earlier archive reference exists', () => {
    const surfaces = guardedSurfaces(reportPending, { stale: 'financial reference' }, null);
    expect(surfaces.archive.pending).toBeNull();
    expect(surfaces.archive.retry).toBe(false);
    expect(surfaces.workspaceStatusVisible).toBe(false);
    expect(surfaces.report.visible).toBe(true);
  });

  it('a pending financial operation keeps the archive panel, its retry and the workspace status, and shows no report panel', () => {
    const surfaces = guardedSurfaces(financialPending, null, null);
    expect(surfaces.workspaceStatusVisible).toBe(true);
    expect(surfaces.archive).toEqual({ visible: true, pending: financialPending, retry: true });
    expect(surfaces.report).toEqual({ visible: false, pending: null, retry: false });
  });

  it('with nothing pending each panel appears only for its own confirmed reference and offers no retry', () => {
    expect(guardedSurfaces(null, null, null)).toEqual({ workspaceStatusVisible: true,
      archive: { visible: false, pending: null, retry: false }, report: { visible: false, pending: null, retry: false } });
    const archiveOnly = guardedSurfaces(null, { kind: 'ref' }, null);
    expect(archiveOnly.archive.visible).toBe(true); expect(archiveOnly.report.visible).toBe(false);
    const reportOnly = guardedSurfaces(null, null, { kind: 'ref' });
    expect(reportOnly.report.visible).toBe(true); expect(reportOnly.archive.visible).toBe(false);
    expect(reportOnly.report.retry).toBe(false);
  });

  it('the report panel given the pending item shows the unknown-outcome hint and the explicit reconcile control', async () => {
    const surfaces = guardedSurfaces(reportPending, null, null);
    await i18n.changeLanguage('en');
    const html = renderToStaticMarkup(createElement(GuardedCsvReportPanel, { api: new AccountApi(), reference: null, pending: surfaces.report.pending,
      onRecovered: () => undefined, onRetry: surfaces.report.retry ? async () => undefined : undefined }));
    expect(html).toContain(guardedTranslations.en.guardedCsvReportUnknownHint);
    expect(html).toContain(operation);
    expect(html).toContain(guardedTranslations.en.guardedReconcile);
  });
});
