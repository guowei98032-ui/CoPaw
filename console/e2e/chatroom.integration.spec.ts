import { test, expect } from '@playwright/test';

// Real agent IDs from system
const REAL_AGENTS = ['Ls9Gr3', 'ztNTTm', 'default', 'CoPaw_QA_Agent_0.1beta1'];

test.describe('Chatroom API Integration Tests', () => {
  test('should list existing chatrooms', async ({ page }) => {
    const response = await page.request.get('http://127.0.0.1:8088/api/chatroom');
    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    // Should have at least the user's chatroom
    expect(data.length).toBeGreaterThan(0);
  });

  test('should create chatroom with real agents', async ({ page }) => {
    const response = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: 'E2E API测试聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [REAL_AGENTS[1], REAL_AGENTS[2]],
      },
    });
    expect(response.status()).toBe(201);
    const data = await response.json();
    expect(data.room.name).toBe('E2E API测试聊天室');
    expect(data.room.lead_agent_id).toBe(REAL_AGENTS[0]);
    expect(data.room.agent_ids).toContain(REAL_AGENTS[1]);

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${data.room.id}`);
  });

  test('should reject creating chatroom with fake agent', async ({ page }) => {
    const response = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '假Agent聊天室',
        lead_agent_id: 'fake-agent-123',
        agent_ids: [],
      },
    });
    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.detail).toContain('not found');
  });

  test('should reject creating chatroom with fake worker agent', async ({ page }) => {
    const response = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '假Worker聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: ['fake-worker-456'],
      },
    });
    expect(response.status()).toBe(400);
    const data = await response.json();
    expect(data.detail).toContain('not found');
  });

  test('should get chatroom by id', async ({ page }) => {
    // Create a chatroom first
    const createResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '查询测试聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [],
      },
    });
    const createData = await createResp.json();
    const roomId = createData.room.id;

    // Get the chatroom
    const getResp = await page.request.get(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
    expect(getResp.status()).toBe(200);
    const getData = await getResp.json();
    expect(getData.id).toBe(roomId);
    expect(getData.name).toBe('查询测试聊天室');

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
  });

  test('should update chatroom', async ({ page }) => {
    // Create a chatroom first
    const createResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '更新测试聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [],
      },
    });
    const createData = await createResp.json();
    const roomId = createData.room.id;

    // Update the chatroom
    const updateResp = await page.request.put(`http://127.0.0.1:8088/api/chatroom/${roomId}`, {
      data: {
        name: '已更新聊天室',
        agent_ids: [REAL_AGENTS[1]],
      },
    });
    expect(updateResp.status()).toBe(200);
    const updateData = await updateResp.json();
    expect(updateData.name).toBe('已更新聊天室');
    expect(updateData.agent_ids).toContain(REAL_AGENTS[1]);

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
  });

  test('should delete chatroom', async ({ page }) => {
    // Create a chatroom first
    const createResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '删除测试聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [],
      },
    });
    const createData = await createResp.json();
    const roomId = createData.room.id;

    // Delete the chatroom
    const deleteResp = await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
    expect(deleteResp.status()).toBe(200);

    // Verify it's deleted
    const getResp = await page.request.get(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
    expect(getResp.status()).toBe(404);
  });

  test('should create task in chatroom', async ({ page }) => {
    // Create a chatroom first
    const roomResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '任务测试聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [REAL_AGENTS[1]],
      },
    });
    const roomData = await roomResp.json();
    const roomId = roomData.room.id;

    // Create a task
    const taskResp = await page.request.post(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks`, {
      data: {
        subject: 'E2E测试任务',
        description: '这是一个E2E测试任务',
        owner: REAL_AGENTS[1],
        priority: 'high',
      },
    });
    expect(taskResp.status()).toBe(201);
    const taskData = await taskResp.json();
    expect(taskData.subject).toBe('E2E测试任务');
    expect(taskData.owner).toBe(REAL_AGENTS[1]);
    expect(taskData.status).toBe('pending');

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
  });

  test('should reject creating task with fake owner', async ({ page }) => {
    // Create a chatroom first
    const roomResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '验证测试聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [],
      },
    });
    const roomData = await roomResp.json();
    const roomId = roomData.room.id;

    // Try to create task with fake owner
    const taskResp = await page.request.post(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks`, {
      data: {
        subject: '假Agent任务',
        owner: 'fake-worker-456',
      },
    });
    expect(taskResp.status()).toBe(400);
    const taskData = await taskResp.json();
    expect(taskData.detail).toContain('not found');

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
  });

  test('should list and update task status', async ({ page }) => {
    // Create a chatroom with task
    const roomResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '任务状态测试',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [REAL_AGENTS[1]],
      },
    });
    const roomData = await roomResp.json();
    const roomId = roomData.room.id;

    const taskResp = await page.request.post(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks`, {
      data: {
        subject: '状态变更任务',
        owner: REAL_AGENTS[1],
      },
    });
    const taskData = await taskResp.json();
    const taskId = taskData.id;

    // List tasks
    const listResp = await page.request.get(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks`);
    expect(listResp.status()).toBe(200);
    const tasks = await listResp.json();
    expect(tasks.length).toBe(1);

    // Update task status to in_progress
    const updateResp = await page.request.put(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks/${taskId}`, {
      data: {
        status: 'in_progress',
        progress: 50,
      },
    });
    expect(updateResp.status()).toBe(200);
    const updatedTask = await updateResp.json();
    expect(updatedTask.status).toBe('in_progress');
    expect(updatedTask.progress).toBe(50);

    // Complete the task
    const completeResp = await page.request.put(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks/${taskId}`, {
      data: {
        status: 'completed',
        progress: 100,
      },
    });
    expect(completeResp.status()).toBe(200);
    const completedTask = await completeResp.json();
    expect(completedTask.status).toBe('completed');
    expect(completedTask.completed_at).not.toBeNull();

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
  });

  test('should send and list messages', async ({ page }) => {
    // Create a chatroom
    const roomResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '消息测试聊天室',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [REAL_AGENTS[1]],
      },
    });
    const roomData = await roomResp.json();
    const roomId = roomData.room.id;

    // Send a message
    const msgResp = await page.request.post(`http://127.0.0.1:8088/api/chatroom/${roomId}/messages`, {
      data: {
        content: 'Hello from E2E test',
        message_type: 'chat',
        to_agent: REAL_AGENTS[1],
      },
    });
    expect(msgResp.status()).toBe(201);
    const msgData = await msgResp.json();
    expect(msgData.content).toBe('Hello from E2E test');
    expect(msgData.to_agent).toBe(REAL_AGENTS[1]);

    // List messages
    const listResp = await page.request.get(`http://127.0.0.1:8088/api/chatroom/${roomId}/messages`);
    expect(listResp.status()).toBe(200);
    const messages = await listResp.json();
    expect(messages.length).toBeGreaterThan(0);

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
  });

  test('should handle multi-agent collaboration', async ({ page }) => {
    // Create a chatroom with multiple agents
    const roomResp = await page.request.post('http://127.0.0.1:8088/api/chatroom', {
      data: {
        name: '多Agent协作测试',
        lead_agent_id: REAL_AGENTS[0],
        agent_ids: [REAL_AGENTS[1], REAL_AGENTS[2]],
      },
    });
    expect(roomResp.status()).toBe(201);
    const roomData = await roomResp.json();
    const roomId = roomData.room.id;

    // Create multiple tasks for different agents
    const task1Resp = await page.request.post(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks`, {
      data: { subject: 'Task for Worker 1', owner: REAL_AGENTS[1] },
    });
    const task2Resp = await page.request.post(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks`, {
      data: { subject: 'Task for Worker 2', owner: REAL_AGENTS[2] },
    });
    expect(task1Resp.status()).toBe(201);
    expect(task2Resp.status()).toBe(201);

    // List all tasks
    const tasksResp = await page.request.get(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks`);
    const tasks = await tasksResp.json();
    expect(tasks.length).toBe(2);

    // Handoff task from worker 1 to worker 2
    const task1Data = await task1Resp.json();
    const handoffResp = await page.request.put(`http://127.0.0.1:8088/api/chatroom/${roomId}/tasks/${task1Data.id}`, {
      data: { owner: REAL_AGENTS[2] },
    });
    expect(handoffResp.status()).toBe(200);
    const handoffTask = await handoffResp.json();
    expect(handoffTask.owner).toBe(REAL_AGENTS[2]);

    // Cleanup
    await page.request.delete(`http://127.0.0.1:8088/api/chatroom/${roomId}`);
  });
});