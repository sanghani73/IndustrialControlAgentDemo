from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request
from config import db


def register_routes(app: Flask):

    @app.route("/")
    def overview():
        return render_template("overview.html")

    @app.route("/actions")
    def actions_page():
        return render_template("actions.html")

    @app.route("/production")
    def production_page():
        return render_template("production.html")

    @app.route("/alarms")
    def alarms_page():
        return render_template("alarms.html")

    # --- JSON API endpoints ---

    @app.route("/api/stats")
    def api_stats():
        active_alarm_groups = db.correlated_alarm_groups.count_documents(
            {"status": "pending_remediation"}
        )
        pending_actions = db.action_queue.count_documents({"status": "proposed"})
        running_batches = db.production_actuals.count_documents({"status": "running"})
        delayed_batches = db.production_actuals.count_documents(
            {"status": "running", "delays": {"$ne": []}}
        )
        completed_actions = db.action_queue.count_documents({"status": "completed"})
        rejected_actions = db.action_queue.count_documents({"status": "rejected"})

        return jsonify({
            "active_alarm_groups": active_alarm_groups,
            "pending_actions": pending_actions,
            "running_batches": running_batches,
            "delayed_batches": delayed_batches,
            "completed_actions": completed_actions,
            "rejected_actions": rejected_actions,
        })

    @app.route("/api/actions")
    def api_actions():
        status_filter = request.args.get("status")
        query = {}
        if status_filter and status_filter != "all":
            query["status"] = status_filter

        actions = list(
            db.action_queue.find(query, {"_id": 0})
            .sort("created_at", -1)
            .limit(50)
        )
        for a in actions:
            for key in ("created_at", "updated_at", "approved_at", "completed_at"):
                if isinstance(a.get(key), datetime):
                    a[key] = a[key].isoformat()
        return jsonify(actions)

    @app.route("/api/actions/<action_id>/approve", methods=["POST"])
    def api_approve_action(action_id):
        result = db.action_queue.update_one(
            {"action_id": action_id, "status": "proposed"},
            {
                "$set": {
                    "status": "approved",
                    "approved_by": "operator",
                    "approved_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.modified_count == 0:
            return jsonify({"error": "Action not found or not in proposed state"}), 404

        db.action_queue.update_one(
            {"action_id": action_id, "status": "approved"},
            {
                "$set": {
                    "status": "executing",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        db.action_queue.update_one(
            {"action_id": action_id, "status": "executing"},
            {
                "$set": {
                    "status": "completed",
                    "execution_result": "Setpoint changes applied successfully",
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        action = db.action_queue.find_one({"action_id": action_id})
        if action and action.get("correlation_group_id"):
            db.correlated_alarm_groups.update_one(
                {"group_id": action["correlation_group_id"]},
                {"$set": {"status": "remediated"}},
            )

        return jsonify({"status": "completed", "action_id": action_id})

    @app.route("/api/actions/<action_id>/reject", methods=["POST"])
    def api_reject_action(action_id):
        data = request.get_json() or {}
        reason = data.get("reason", "No reason provided")

        result = db.action_queue.update_one(
            {"action_id": action_id, "status": "proposed"},
            {
                "$set": {
                    "status": "rejected",
                    "rejected_reason": reason,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        if result.modified_count == 0:
            return jsonify({"error": "Action not found or not in proposed state"}), 404

        return jsonify({"status": "rejected", "action_id": action_id})

    @app.route("/api/alarms")
    def api_alarms():
        groups = list(
            db.correlated_alarm_groups.find({}, {"_id": 0})
            .sort("created_at", -1)
            .limit(50)
        )
        for g in groups:
            if isinstance(g.get("created_at"), datetime):
                g["created_at"] = g["created_at"].isoformat()
            alarm_ids = g.pop("alarm_ids", [])
            g["alarm_count"] = len(alarm_ids)
        return jsonify(groups)

    @app.route("/api/production")
    def api_production():
        plans = list(
            db.production_plans.find({}, {"_id": 0}).sort("shift", -1).limit(1)
        )
        plan = plans[0] if plans else None

        actuals = {
            doc["batch_name"]: doc
            for doc in db.production_actuals.find({}, {"_id": 0})
        }

        result = {"plan": plan, "actuals": actuals}

        if plan:
            for batch in plan.get("planned_batches", []):
                actual = actuals.get(batch["batch_name"])
                if actual:
                    batch["actual_status"] = actual.get("status", "unknown")
                    batch["deviation_minutes"] = actual.get(
                        "deviation_from_plan_minutes", 0
                    )
                    batch["delays"] = actual.get("delays", [])
                    for d in batch["delays"]:
                        for key in ("started_at", "resolved_at"):
                            if isinstance(d.get(key), datetime):
                                d[key] = d[key].isoformat()
                    projected = actual.get("projected_finish_at")
                    batch["projected_finish_at"] = (
                        projected.isoformat() if isinstance(projected, datetime) else projected
                    )
                else:
                    batch["actual_status"] = "not_started"
                    batch["deviation_minutes"] = 0
                    batch["delays"] = []
                    batch["projected_finish_at"] = None

                for key in ("planned_start", "planned_end"):
                    if isinstance(batch.get(key), datetime):
                        batch[key] = batch[key].isoformat()

        return jsonify(result)
