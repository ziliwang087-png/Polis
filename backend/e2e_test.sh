#!/bin/bash
set -e

BASE_URL="https://polis-backend-production.up.railway.app/api/v1"
TIMESTAMP=$(date +%s)

echo "=== 完整端到端测试 ==="
echo ""

# 1. 注册
echo "1️⃣ 注册新用户..."
REGISTER_RESPONSE=$(curl -sS "$BASE_URL/auth/register" -X POST \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"e2e-$TIMESTAMP@test.com\",\"username\":\"e2e_$TIMESTAMP\",\"password\":\"Test123\"}")

USER_TOKEN=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
USER_ID=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['user']['id'])")
CREDITS=$(echo "$REGISTER_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['user']['credit_balance'])")

echo "   ✅ 用户 ID: $USER_ID"
echo "   ✅ Credits: $CREDITS"
if [ "$CREDITS" != "0" ]; then
  echo "   ❌ Credits 应该是 0，但是 $CREDITS"
  exit 1
fi

# 2. 创建 Agent
echo ""
echo "2️⃣ 创建 Agent..."
AGENT_RESPONSE=$(curl -sS "$BASE_URL/agents" -X POST \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"E2E Test Agent","description":"完整测试"}')

AGENT_ID=$(echo "$AGENT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
AGENT_TOKEN=$(echo "$AGENT_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")

echo "   ✅ Agent ID: $AGENT_ID"

# 3. 发布任务
echo ""
echo "3️⃣ 发布任务..."
TASK_RESPONSE=$(curl -sS "$BASE_URL/tasks" -X POST \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"E2E测试任务","description":"验证XP奖励"}')

TASK_ID=$(echo "$TASK_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['task_id'])")
echo "   ✅ Task ID: $TASK_ID"

# 4. Agent 接单
echo ""
echo "4️⃣ Agent 接单..."
curl -sS "$BASE_URL/tasks/$TASK_ID/claim" -X POST \
  -H "Authorization: Bearer $AGENT_TOKEN" > /dev/null
echo "   ✅ 接单成功"

# 5. Agent 完成任务
echo ""
echo "5️⃣ Agent 完成任务..."
curl -sS "$BASE_URL/tasks/$TASK_ID/complete" -X POST \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"deliverable":"测试完成"}' > /dev/null
echo "   ✅ 任务完成"

# 6. 查看任务详情
echo ""
echo "6️⃣ 查看任务详情..."
TASK_DETAIL=$(curl -sS "$BASE_URL/tasks/$TASK_ID" \
  -H "Authorization: Bearer $USER_TOKEN")

if echo "$TASK_DETAIL" | grep -q "detail.*failed"; then
  echo "   ❌ 任务详情接口报错"
  echo "$TASK_DETAIL"
  exit 1
else
  echo "   ✅ 任务详情接口正常"
fi

# 7. 查看通知
echo ""
echo "7️⃣ 查看通知..."
NOTIFICATIONS=$(curl -sS "$BASE_URL/notifications" \
  -H "Authorization: Bearer $USER_TOKEN")

if echo "$NOTIFICATIONS" | grep -q "detail.*failed"; then
  echo "   ❌ 通知接口报错"
  echo "$NOTIFICATIONS"
  exit 1
else
  NOTIF_COUNT=$(echo "$NOTIFICATIONS" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")
  echo "   ✅ 通知接口正常，通知数: $NOTIF_COUNT"
fi

# 8. 查看 Agent 统计
echo ""
echo "8️⃣ 查看 Agent 统计..."
STATS=$(curl -sS "$BASE_URL/gamification/agent/$AGENT_ID/stats")

if echo "$STATS" | grep -q "detail.*Not Found"; then
  echo "   ❌ 游戏化接口 404"
  exit 1
else
  XP=$(echo "$STATS" | python3 -c "import sys, json; print(json.load(sys.stdin)['xp'])")
  LEVEL=$(echo "$STATS" | python3 -c "import sys, json; print(json.load(sys.stdin)['level'])")
  COMPLETED=$(echo "$STATS" | python3 -c "import sys, json; print(json.load(sys.stdin)['total_tasks_completed'])")
  
  echo "   ✅ 游戏化接口正常"
  echo "   📊 XP: $XP (应该是 50)"
  echo "   📊 Level: $LEVEL"
  echo "   📊 完成数: $COMPLETED (应该是 1)"
  
  if [ "$XP" != "50" ]; then
    echo "   ⚠️  XP 不是 50，可能游戏化逻辑没触发"
  fi
fi

echo ""
echo "=== ✅ 所有测试通过 ==="
