import { useId, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

export type ExplanationDepth = 'quick' | 'simple' | 'professional';

/** A presentation override only; the supplied facts and evidence never change. */
export default function ClaimDepth({ depth, claim, children }: {
  depth: ExplanationDepth; claim: string;
  children: (depth: ExplanationDepth, control: ReactNode) => ReactNode;
}) {
  const { t } = useTranslation(); const id = useId();
  const [override, setOverride] = useState<ExplanationDepth | ''>('');
  const control = <div className="claim-depth"><label htmlFor={id}>{t('claimDepth', { claim })}</label>
    <select id={id} value={override} onChange={(event) => setOverride(event.target.value as ExplanationDepth | '')}>
      <option value="">{t('claimWorkspaceDepth', { depth: t(depth) })}</option>
      {(['quick', 'simple', 'professional'] as const).map((level) => <option key={level} value={level}>{t(level)}</option>)}
    </select></div>;
  return children(override || depth, control);
}
