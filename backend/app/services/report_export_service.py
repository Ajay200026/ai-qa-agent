import io
import json
import zipfile
from pathlib import Path
from uuid import UUID

from fpdf import FPDF
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.report_repository import ReportRepository
from app.services.artifact_service import (
    artifact_basename,
    execution_artifacts_dir,
    list_artifact_files,
    resolve_artifact_path,
)


def _pdf_safe(text: str | None) -> str:
    """Helvetica only supports Latin-1; replace unsupported characters."""
    if not text:
        return ""
    return text.encode("latin-1", errors="replace").decode("latin-1")


class ReportExportService:
    def __init__(self, db: AsyncSession):
        self.report_repo = ReportRepository(db)
        self.execution_repo = ExecutionRepository(db)

    async def _load_report_context(self, report_id: UUID):
        report = await self.report_repo.get_by_id(report_id)
        if not report:
            raise NotFoundError("Report", report_id)
        execution = await self.execution_repo.get_with_steps(report.execution_id)
        if not execution:
            raise NotFoundError("Execution", report.execution_id)
        return report, execution

    def _step_screenshot_path(self, execution_id: UUID, screenshot_path: str | None) -> Path | None:
        basename = artifact_basename(screenshot_path)
        if not basename:
            return None
        try:
            return resolve_artifact_path(execution_id, basename)
        except NotFoundError:
            return None

    def _build_summary_text(self, report, execution) -> str:
        lines = [
            f"Report ID: {report.id}",
            f"Execution ID: {report.execution_id}",
            f"Result: {'PASSED' if report.failed_count == 0 else 'FAILED'}",
            f"Passed: {report.passed_count}",
            f"Failed: {report.failed_count}",
            f"Created: {report.created_at.isoformat()}",
            "",
            "=== Summary ===",
            report.summary,
        ]
        if report.llm_analysis:
            lines.extend(["", "=== LLM Analysis ===", report.llm_analysis])
        lines.extend(["", "=== Steps ==="])
        for step in sorted(execution.steps, key=lambda s: s.seq):
            lines.append(
                f"{step.seq}. {step.name} [{step.status}] action={step.action}"
                + (f" error={step.error}" if step.error else "")
            )
        return "\n".join(lines)

    def _build_report_json(self, report, execution) -> dict:
        return {
            "report": {
                "id": str(report.id),
                "execution_id": str(report.execution_id),
                "summary": report.summary,
                "passed_count": report.passed_count,
                "failed_count": report.failed_count,
                "llm_analysis": report.llm_analysis,
                "created_at": report.created_at.isoformat(),
            },
            "steps": [
                {
                    "seq": step.seq,
                    "name": step.name,
                    "action": step.action,
                    "status": step.status,
                    "error": step.error,
                    "screenshot": artifact_basename(step.screenshot_path),
                }
                for step in sorted(execution.steps, key=lambda s: s.seq)
            ],
        }

    async def build_zip(self, report_id: UUID) -> tuple[bytes, str]:
        report, execution = await self._load_report_context(report_id)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("report_summary.txt", self._build_summary_text(report, execution))
            zf.writestr(
                "report.json",
                json.dumps(self._build_report_json(report, execution), indent=2),
            )
            artifacts_dir = execution_artifacts_dir(report.execution_id)
            for filename in list_artifact_files(report.execution_id):
                filepath = artifacts_dir / filename
                zf.write(filepath, f"screenshots/{filename}")
        filename = f"report-{str(report.id)[:8]}.zip"
        return buffer.getvalue(), filename

    async def build_pdf(self, report_id: UUID) -> tuple[bytes, str]:
        report, execution = await self._load_report_context(report_id)
        try:
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Execution Report", ln=True)
            pdf.set_font("Helvetica", size=11)
            passed = report.failed_count == 0
            pdf.cell(0, 8, f"Report ID: {report.id}", ln=True)
            pdf.cell(0, 8, f"Execution ID: {report.execution_id}", ln=True)
            pdf.cell(0, 8, f"Result: {'PASSED' if passed else 'FAILED'}", ln=True)
            pdf.cell(0, 8, f"Passed: {report.passed_count}  Failed: {report.failed_count}", ln=True)
            pdf.cell(0, 8, f"Created: {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}", ln=True)
            pdf.ln(4)

            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Summary", ln=True)
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(0, 6, _pdf_safe(report.summary))
            pdf.ln(2)

            if report.llm_analysis:
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, "LLM Analysis", ln=True)
                pdf.set_font("Helvetica", size=10)
                pdf.multi_cell(0, 6, _pdf_safe(report.llm_analysis))
                pdf.ln(2)

            for step in sorted(execution.steps, key=lambda s: s.seq):
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(0, 8, _pdf_safe(f"Step {step.seq}: {step.name}"), ln=True)
                pdf.set_font("Helvetica", size=10)
                pdf.cell(
                    0,
                    6,
                    _pdf_safe(f"Action: {step.action}  Status: {step.status}"),
                    ln=True,
                )
                if step.error:
                    pdf.set_text_color(200, 0, 0)
                    pdf.multi_cell(0, 6, _pdf_safe(f"Error: {step.error}"))
                    pdf.set_text_color(0, 0, 0)
                screenshot = self._step_screenshot_path(report.execution_id, step.screenshot_path)
                if screenshot:
                    pdf.ln(4)
                    try:
                        pdf.image(str(screenshot), w=190)
                    except Exception:
                        pdf.cell(0, 6, "(screenshot could not be embedded)", ln=True)

            filename = f"report-{str(report.id)[:8]}.pdf"
            return bytes(pdf.output()), filename
        except Exception as exc:
            raise BadRequestError(f"Failed to generate PDF report: {exc}") from exc
