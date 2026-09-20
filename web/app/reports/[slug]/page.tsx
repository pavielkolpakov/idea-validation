import { ReportView } from "@/components/report-view";
export default async function ReportPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ReportView key={slug} slug={slug} />;
}
