export const ORG_TYPES = [
  { value: "production", label: "Production" },
  { value: "sandbox", label: "Sandbox" },
  { value: "scratch", label: "Scratch" },
  { value: "custom", label: "Custom / Dev / Partner" },
] as const;

export function loginUrlForOrgType(orgType: string, customUrl: string): string {
  if (orgType === "production") return "https://login.salesforce.com";
  if (orgType === "sandbox" || orgType === "scratch") return "https://test.salesforce.com";
  return customUrl.trim();
}
