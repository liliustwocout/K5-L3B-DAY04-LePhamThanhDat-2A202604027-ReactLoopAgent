import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import SYSTEM_PROMPT, run_agent
from status_tools import StatusTools
from test_lab import FakeProvider, final, tool_call


class PromptTests(unittest.TestCase):
    def test_prompt_is_sent_with_key_rules(self):
        fake = FakeProvider([final('Không đủ dữ liệu.')])
        run_agent('x', fake, StatusTools())
        system = fake.histories[0][0]
        self.assertEqual(system['role'], 'system')
        self.assertEqual(system['content'], SYSTEM_PROMPT)
        for phrase in ('KHÔNG phải trạng thái dịch vụ', '50 incident gần nhất', 'captured_at'):
            self.assertIn(phrase, SYSTEM_PROMPT)

    def test_timeout_is_observation_not_crash(self):
        fake = FakeProvider([tool_call('t', 'get_status', '{"provider":"cloudflare"}'), final('Không kiểm tra được Cloudflare.')])
        result = run_agent('x', fake, StatusTools(fail=True))
        self.assertEqual(result['status'], 'completed')
        observation = json.loads(fake.histories[1][-1]['content'])
        self.assertFalse(observation['ok'])
        self.assertEqual(observation['error'], 'TimeoutError')


class DeferTests(unittest.TestCase):
    def test_incident_deferred_when_batched_with_status(self):
        a = tool_call('a', 'get_status', '{"provider":"github"}')
        b = tool_call('b', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
        a['calls'] += b['calls']
        a['message']['tool_calls'] += b['message']['tool_calls']
        retry = tool_call('c', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
        fake = FakeProvider([a, retry, final('Xong https://stspg.io/pjgptg3cfc6n')])
        result = run_agent('x', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertEqual([m['tool_call_id'] for m in fake.histories[1][-2:]], ['a', 'b'])
        self.assertEqual(json.loads(fake.histories[1][-1]['content'])['error'], 'DEFERRED')
        self.assertTrue(any(x['event'] == 'deferred_call' for x in result['trace']))
        steps = {x['step'] for x in result['trace'] if x['event'] == 'tool'}
        self.assertEqual(steps, {1, 2})

    def test_two_status_calls_not_deferred(self):
        a = tool_call('a', 'get_status', '{"provider":"github"}')
        b = tool_call('b', 'get_status', '{"provider":"cloudflare"}')
        a['calls'] += b['calls']
        a['message']['tool_calls'] += b['message']['tool_calls']
        result = run_agent('x', FakeProvider([a, final()]), StatusTools())
        self.assertFalse(any(x['event'] == 'deferred_call' for x in result['trace']))


class GateTests(unittest.TestCase):
    def test_deferred_incident_is_requested_before_completion(self):
        a = tool_call('a', 'get_status', '{"provider":"github"}')
        b = tool_call('b', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
        a['calls'] += b['calls']
        a['message']['tool_calls'] += b['message']['tool_calls']
        retry = tool_call('c', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}')
        fake = FakeProvider([a, final('Bỏ qua'), retry, final('Xong https://stspg.io/pjgptg3cfc6n')])
        result = run_agent('x', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(x['event'] == 'validation_deferred_incident' for x in result['trace']))

    def test_incident_without_status_requests_get_status_once(self):
        url = 'https://stspg.io/pjgptg3cfc6n'
        fake = FakeProvider([tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
                             final('Đã xử lý ' + url), tool_call('2', 'get_status', '{"provider":"github"}'), final('Xong ' + url)])
        result = run_agent('x', fake, StatusTools())
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(x['event'] == 'validation_missing_status' for x in result['trace']))
        # gate chỉ nhắc một lần: không có model call thừa nếu model vẫn không gọi get_status
        fake2 = FakeProvider([tool_call('1', 'get_incident_details', '{"provider":"github","incident_id":"xr3myzj7ms51"}'),
                              final('A ' + url), final('B ' + url)])
        self.assertEqual(run_agent('x', fake2, StatusTools())['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
