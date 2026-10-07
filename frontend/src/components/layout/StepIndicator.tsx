import { Check } from 'lucide-react';
export type Step = 'input' | 'plan' | 'generate' | 'export';
const steps: { id: Step; label: string }[] = [{ id:'input',label:'整理内容' },{ id:'plan',label:'规划大纲' },{ id:'generate',label:'制作页面' },{ id:'export',label:'导出文件' }];
export function StepIndicator({ currentStep, progress }: { currentStep: Step; progress: number }) {
 const current = steps.findIndex(step => step.id === currentStep);
 return <ol className="workflow-steps" aria-label="演示制作进度">{steps.map((step,index) => { const done = index < current || (index === current && progress === 100); return <li key={step.id} className={done ? 'done' : index === current ? 'current' : ''} aria-current={index === current ? 'step' : undefined}><span>{done ? <Check size={12} /> : `0${index+1}`}</span>{step.label}</li>; })}</ol>;
}
