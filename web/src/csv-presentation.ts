import type { TFunction } from 'i18next';

/** Human recovery text only. The canonical code and source detail stay in the report. */
export function csvIssueLabel(t: TFunction, code: string): string {
  return t(`csvIssue_${code}`, { keySeparator: false, defaultValue: t('csvIssueGeneric') });
}
