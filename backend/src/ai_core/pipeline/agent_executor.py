from __future__ import annotations

from typing import Dict, Any, List, Optional
import time

from shared.config.tuning import agents as agent_cfg
from shared.metrics.agent_metrics import agent_metrics
from shared.security.policy import Policy
from ai_core.pipeline.audit_service import write_audit
import logging


class AgentExecutor:
    def __init__(self, agent_cls) -> None:
        self.agent = agent_cls()

    def run(self, goal: str, tenant_id: str, claims: Dict[str, Any], db) -> Dict[str, Any]:
        if not agent_cfg.enabled:
            return {"ok": False, "error": "agents_disabled"}
        t0 = time.time()
        name = getattr(self.agent, 'name', 'agent')
        plan: List[Dict[str, Any]] = []
        try:
            plan = self.agent.plan(goal, {"tenant_id": tenant_id})[:agent_cfg.max_steps]
        except Exception as e:
            agent_metrics.inc_failure(name, tenant_id)
            logging.getLogger(__name__).exception("[agent.plan] error", extra={"tenant_id": tenant_id, "action": "agent.exec", "agent": name})
            return {"ok": False, "error": str(e)}
        steps_out: List[Dict[str, Any]] = []
        for step in plan:
            action = str(step.get("action", "")).strip()
            params = step.get("params", {}) or {}
            if not action:
                continue
            # Policy pre-check
            perm = f"agent:action:{action}"
            if not Policy.allowed(claims, perm, resource={"classification": "internal"}):
                agent_metrics.inc_denied(name, tenant_id, action)
                steps_out.append({"action": action, "status": "denied"})
                # audit denial
                try:
                    write_audit(db, tenant_id, claims.get("user_id"), f"policy.denied:{perm}", "agent", goal, str(params), False, int((time.time()-t0)*1000), category="agent", auth_type=claims.get("auth_type"))
                except Exception:
                    pass
                continue
            # Execute tool
            try:
                agent_metrics.inc_action(name, tenant_id, action)
                tool = self.agent.tools().get(action)
                if not tool:
                    raise RuntimeError("unknown_action")
                res = tool(tenant_id, params)
                steps_out.append({"action": action, "status": "ok", "result": res})
                try:
                    write_audit(db, tenant_id, claims.get("user_id"), f"agent.execute:{action}", "agent", goal, str(res)[:500], True, int((time.time()-t0)*1000), category="agent", auth_type=claims.get("auth_type"))
                except Exception:
                    pass
            except Exception as e:
                agent_metrics.inc_failure(name, tenant_id)
                logging.getLogger(__name__).exception("[agent.execute] error", extra={"tenant_id": tenant_id, "action": action, "agent": name})
                steps_out.append({"action": action, "status": "error", "error": str(e)})
        dur = time.time() - t0
        agent_metrics.observe_duration(name, dur)
        if any(s.get("status") == "ok" for s in steps_out):
            agent_metrics.inc_success(name, tenant_id)
        return {"ok": True, "agent": name, "steps": steps_out, "elapsed_ms": int(dur*1000)}


