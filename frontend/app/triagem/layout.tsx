import { WizardProvider } from "@/components/triagem/wizard-engine";

export default function TriagemLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WizardProvider>{children}</WizardProvider>;
}
