import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import { GUARDED_OPERATIONS, GUARDED_PROFILE, GUARDED_UNSUPPORTED, type GuardedProfile, type PendingGuardedOperation } from './guarded';
import { SCHEMA } from './transport';

// Behavioural wiring test: the guarded-surface rules are tested on guardedSurfaces() itself (guarded-pending.test.ts), which proves
// nothing if App stops calling it, calls it with the wrong arguments, or ignores what it returns. Here App is rendered for real
// (server render, no browser, no new package) in states a fresh App never has:
//  * ./guarded-pending is replaced by a recording wrapper around the real function (the arguments, and which fields App reads);
//  * the two guarded panels are replaced by stubs that record the props App gives them (they are tested on their own);
//  * react's useState is wrapped so that a render can START with chosen state. A server render runs no effect, so there is no other
//    way to put a pending operation, a reference or a session into App without a DOM or a new package. The wrapper finds the states
//    by the initial values of App's own hooks (see locate()), so a reordering of those hooks fails the test loudly, never silently.
// Fictional state only: invented identifiers, no request, no storage.
const harness = vi.hoisted(() => ({
  calls: [] as unknown[][],
  reads: new Set<string | symbol>(),
  initials: [] as unknown[], // the initial value of every useState call of the current render, in call order
  overrides: new Map<number, unknown>(), // call index -> the state the render starts with
  archivePanels: [] as Record<string, unknown>[],
  reportPanels: [] as Record<string, unknown>[],
}));

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react')>();
  return {
    ...actual,
    useState: (initial: unknown) => {
      const index = harness.initials.length;
      harness.initials.push(initial);
      return (actual.useState as (value: unknown) => unknown)(harness.overrides.has(index) ? harness.overrides.get(index) : initial);
    },
  };
});

vi.mock('./guarded-pending', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./guarded-pending')>();
  return {
    ...actual,
    guardedSurfaces: (...args: Parameters<typeof actual.guardedSurfaces>) => {
      harness.calls.push(args);
      return new Proxy(actual.guardedSurfaces(...args), {
        get(target, key, receiver) { harness.reads.add(key); return Reflect.get(target, key, receiver); },
      });
    },
  };
});

vi.mock('./GuardedArchivePanel', async () => {
  const { createElement: h } = await import('react');
  return { default: (props: Record<string, unknown>) => { harness.archivePanels.push(props); return h('section', { 'data-panel': 'archive' }); } };
});
vi.mock('./GuardedCsvReportPanel', async () => {
  const { createElement: h } = await import('react');
  return { default: (props: Record<string, unknown>) => { harness.reportPanels.push(props); return h('section', { 'data-panel': 'report' }); } };
});

const PROFILE: GuardedProfile = {
  schema: 'finweb.guarded_profile/1', profile: GUARDED_PROFILE, synthetic: true, saved_only: true, source_as_of: '2026-01-02',
  opening_date_required: true, opening_date_max: '2026-01-02', opening_date_recommended: '2026-01-01', selector: 'CP5_DIVERSIFICATION',
  operations: GUARDED_OPERATIONS, unsupported: GUARDED_UNSUPPORTED,
};
const SESSION = { schema_version: SCHEMA, authenticated: true, user: { user_id: 'fictional-user', username: 'fictional.user' }, csrf_token: '0'.repeat(64), guarded_profile: PROFILE };

// invented, distinct objects: App must hand each one to the place it belongs, and identity (toBe) tells them apart
const FINANCIAL_PENDING: PendingGuardedOperation = { operationId: '11111111-1111-4111-8111-111111111111', portfolioId: 'fictional-portfolio' };
const REPORT_PENDING: PendingGuardedOperation = { operationId: '22222222-2222-4222-8222-222222222222', portfolioId: 'fictional-portfolio', kind: 'CSV_REPORT' };
const ARCHIVE_REFERENCE = { portfolio_id: 'fictional-portfolio', operation_id: 'archive-operation', revision_id: 'archive-revision' };
const REPORT_REFERENCE = { portfolio_id: 'fictional-portfolio', operation_id: 'report-operation', report_id: 'report-id' };

interface Start { pending?: PendingGuardedOperation | null; archive?: unknown; report?: unknown; status?: string; session?: boolean }
type Rendered = { markup: string; initials: unknown[] };

async function render(overrides: Map<number, unknown>): Promise<Rendered> {
  await import('./i18n');
  const { default: App } = await import('./App');
  harness.calls.length = 0; harness.reads.clear(); harness.archivePanels.length = 0; harness.reportPanels.length = 0;
  harness.initials.length = 0; harness.overrides = overrides;
  const markup = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ['/overview'] }, createElement(App)));
  harness.overrides = new Map();
  return { markup, initials: [...harness.initials] };
}

/** Where App's own hooks are, from the initial values of its useState calls (App runs before any child). Throws if they moved. */
function locate(initials: unknown[]): { archive: number; pending: number; report: number; status: number; session: number } {
  // guardedReference, guardedPending, guardedCsvReportReference (null, null, null), after realReadinessOpen (false), before csvReportRecovery (0)
  const guarded = initials.findIndex((value, i) => i > 0 && value === null && initials[i + 1] === null && initials[i + 2] === null && initials[i + 3] === 0 && initials[i - 1] === false);
  // workspaceStatus (''), session (null), checkingAccount (true)
  const status = initials.findIndex((value, i) => value === '' && initials[i + 1] === null && initials[i + 2] === true);
  if (guarded < 0 || status < 0) throw new Error('cannot locate the guarded states of App by their initial values: App\'s useState order changed, update locate()');
  return { archive: guarded, pending: guarded + 1, report: guarded + 2, status, session: status + 1 };
}

let probe: { layout: ReturnType<typeof locate>; initials: unknown[] } | null = null;
async function renderApp(start: Start = {}): Promise<Rendered> {
  if (probe === null) { const first = (await render(new Map())).initials; probe = { layout: locate(first), initials: first }; }
  const { layout, initials } = probe;
  const overrides = new Map<number, unknown>();
  if (start.archive !== undefined) overrides.set(layout.archive, start.archive);
  if (start.pending !== undefined) overrides.set(layout.pending, start.pending);
  if (start.report !== undefined) overrides.set(layout.report, start.report);
  if (start.status !== undefined) overrides.set(layout.status, start.status);
  if (start.session) overrides.set(layout.session, SESSION);
  const rendered = await render(overrides);
  // the hooks are the ones the probe saw, in the same order: the overrides landed where they were meant to
  expect(rendered.initials.slice(0, layout.report + 1)).toEqual(initials.slice(0, layout.report + 1));
  return rendered;
}

const STATUS_TEXT = 'The saved revision is confirmed.'; // English text of the workspace status 'revisionSaved'
function statusLine(markup: string): string {
  const match = /<div class="async-status"[^>]*>([^<]*)<\/div>/.exec(markup);
  if (match === null) throw new Error('the status line is not in the markup');
  return match[1];
}
const lastCall = (): unknown[] => harness.calls[harness.calls.length - 1];

describe('App uses guardedSurfaces() from guarded-pending', () => {
  it('calls it on render with the pending operation and both references, all empty on a fresh App', async () => {
    const { markup } = await renderApp();
    expect(markup.length).toBeGreaterThan(0);
    expect(harness.calls.length).toBeGreaterThan(0);
    for (const args of harness.calls) expect(args).toEqual([null, null, null]);
    expect(harness.archivePanels.length + harness.reportPanels.length).toBe(0); // nothing guarded to show
  });

  it('reads the returned surfaces: the workspace status line is governed by workspaceStatusVisible', async () => {
    await renderApp();
    expect(harness.reads.has('workspaceStatusVisible')).toBe(true);
  });

  it('can reach the states below: the harness puts the chosen state into App', async () => {
    await renderApp({ pending: FINANCIAL_PENDING, archive: ARCHIVE_REFERENCE, report: REPORT_REFERENCE, session: true });
    expect(lastCall()[0]).toBe(FINANCIAL_PENDING);
  });
});

describe('App passes its own state, in the right places, and shows what the surfaces say', () => {
  it('passes the pending operation, the archive reference and the report reference, in that order, without substitution', async () => {
    await renderApp({ pending: FINANCIAL_PENDING, archive: ARCHIVE_REFERENCE, report: REPORT_REFERENCE, session: true });
    expect(harness.calls.length).toBeGreaterThan(0);
    for (const args of harness.calls) {
      expect(args).toHaveLength(3);
      expect(args[0]).toBe(FINANCIAL_PENDING); // passing null here is the regression guarded-pending exists to prevent
      expect(args[1]).toBe(ARCHIVE_REFERENCE); // and swapping the two references would show the wrong panel
      expect(args[2]).toBe(REPORT_REFERENCE);
    }
  });

  it('a pending CSV_REPORT operation shows the report panel only, hides the stale workspace status and gives the panel the retry', async () => {
    const { markup } = await renderApp({ pending: REPORT_PENDING, status: 'revisionSaved', session: true });
    expect(lastCall()).toEqual([REPORT_PENDING, null, null]);
    expect(lastCall()[0]).toBe(REPORT_PENDING);
    expect(harness.archivePanels).toHaveLength(0); // the financial archive panel would describe a different operation
    expect(harness.reportPanels).toHaveLength(1);
    expect(harness.reportPanels[0].pending).toBe(REPORT_PENDING);
    expect(harness.reportPanels[0].reference).toBeNull();
    expect(typeof harness.reportPanels[0].onRetry).toBe('function');
    expect(statusLine(markup)).toBe(''); // workspaceStatusVisible is false
    expect(markup).toContain('data-panel="report"');
    expect(markup).not.toContain('data-panel="archive"');
  });

  it('a pending financial operation shows the archive panel only, with the retry, and keeps the workspace status', async () => {
    const { markup } = await renderApp({ pending: FINANCIAL_PENDING, status: 'revisionSaved', session: true });
    expect(lastCall()).toEqual([FINANCIAL_PENDING, null, null]);
    expect(harness.reportPanels).toHaveLength(0);
    expect(harness.archivePanels).toHaveLength(1);
    expect(harness.archivePanels[0].pending).toBe(FINANCIAL_PENDING);
    expect(harness.archivePanels[0].reference).toBeNull();
    expect(typeof harness.archivePanels[0].onRetry).toBe('function');
    expect(statusLine(markup)).toContain(STATUS_TEXT);
  });

  it('with no pending operation the panels follow their own reference: the archive reference opens the archive panel only', async () => {
    const { markup } = await renderApp({ archive: ARCHIVE_REFERENCE, status: 'revisionSaved', session: true });
    expect(lastCall()).toEqual([null, ARCHIVE_REFERENCE, null]);
    expect(harness.reportPanels).toHaveLength(0);
    expect(harness.archivePanels).toHaveLength(1);
    expect(harness.archivePanels[0].reference).toBe(ARCHIVE_REFERENCE);
    expect(harness.archivePanels[0].pending).toBeNull();
    expect(harness.archivePanels[0].onRetry).toBeUndefined(); // nothing is pending, so there is nothing to retry
    expect(statusLine(markup)).toContain(STATUS_TEXT);
  });

  it('with no pending operation the report reference opens the report panel only (the two references are not interchangeable)', async () => {
    const { markup } = await renderApp({ report: REPORT_REFERENCE, status: 'revisionSaved', session: true });
    expect(lastCall()).toEqual([null, null, REPORT_REFERENCE]);
    expect(harness.archivePanels).toHaveLength(0);
    expect(harness.reportPanels).toHaveLength(1);
    expect(harness.reportPanels[0].reference).toBe(REPORT_REFERENCE);
    expect(harness.reportPanels[0].pending).toBeNull();
    expect(harness.reportPanels[0].onRetry).toBeUndefined();
    expect(statusLine(markup)).toContain(STATUS_TEXT);
  });

  it('a pending CSV_REPORT operation is never handed to the archive panel, even when an archive reference opens that panel', async () => {
    await renderApp({ pending: REPORT_PENDING, archive: ARCHIVE_REFERENCE, session: true });
    expect(harness.archivePanels).toHaveLength(1);
    expect(harness.archivePanels[0].reference).toBe(ARCHIVE_REFERENCE);
    expect(harness.archivePanels[0].pending).toBeNull(); // it describes a report, not the financial operation this panel reads
    expect(harness.archivePanels[0].onRetry).toBeUndefined();
    expect(harness.reportPanels).toHaveLength(1);
    expect(harness.reportPanels[0].pending).toBe(REPORT_PENDING);
  });

  it('a pending financial operation is never handed to the report panel, even when a report reference opens that panel', async () => {
    await renderApp({ pending: FINANCIAL_PENDING, report: REPORT_REFERENCE, session: true });
    expect(harness.reportPanels).toHaveLength(1);
    expect(harness.reportPanels[0].reference).toBe(REPORT_REFERENCE);
    expect(harness.reportPanels[0].pending).toBeNull();
    expect(harness.reportPanels[0].onRetry).toBeUndefined();
    expect(harness.archivePanels).toHaveLength(1);
    expect(harness.archivePanels[0].pending).toBe(FINANCIAL_PENDING);
  });

  it('both references together open both panels, each with its own reference', async () => {
    await renderApp({ archive: ARCHIVE_REFERENCE, report: REPORT_REFERENCE, session: true });
    expect(harness.archivePanels.map((p) => p.reference)).toEqual([ARCHIVE_REFERENCE]);
    expect(harness.reportPanels.map((p) => p.reference)).toEqual([REPORT_REFERENCE]);
  });

  it('the panels belong to a guarded, authenticated session: without one nothing guarded is shown, whatever is pending', async () => {
    await renderApp({ pending: FINANCIAL_PENDING, archive: ARCHIVE_REFERENCE, report: REPORT_REFERENCE });
    expect(lastCall()[0]).toBe(FINANCIAL_PENDING); // the surfaces are still computed ...
    expect(harness.archivePanels.length + harness.reportPanels.length).toBe(0); // ... but there is no panel to put them in
  });
});
