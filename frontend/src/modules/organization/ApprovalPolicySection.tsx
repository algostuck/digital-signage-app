import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Card, Checkbox, Space, Typography } from "antd";
import { EntityList } from "@/design-system";
import { api, ApiError } from "../../lib/api";

interface Policy {
  entity_type: string;
  require_approval: boolean;
  maker_checker: boolean;
}

/** P2-APP-001: tenant approval policy controls (part of Tenant Settings). */
export function ApprovalPolicySection({ canManage }: { canManage: boolean }) {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const policiesQuery = useQuery({
    queryKey: ["approval-policies"],
    queryFn: () => api.get<Policy[]>("/approval-policies"),
    enabled: canManage,
  });

  const save = useMutation({
    mutationFn: (policy: Policy) =>
      api.put(`/approval-policies/${policy.entity_type}`, {
        require_approval: policy.require_approval,
        maker_checker: policy.maker_checker,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approval-policies"] }),
    onError: (err) =>
      message.error(err instanceof ApiError ? err.message : "Failed to save policy"),
  });

  if (!canManage) return null;
  const policies = policiesQuery.data?.data ?? [];

  return (
    <Card size="small" title="Approval policies" loading={policiesQuery.isLoading}>
      <Typography.Paragraph type="secondary" className="!mb-2">
        Govern which submissions need review and whether the submitter may decide
        their own request (maker-checker).
      </Typography.Paragraph>
      <EntityList
        dense
        items={policies}
        rowKey="entity_type"
        renderItem={(policy) => (
            <Space wrap size="large">
              <Typography.Text strong className="w-24 inline-block capitalize">
                {policy.entity_type}s
              </Typography.Text>
              <Checkbox
                checked={policy.require_approval}
                onChange={(e) =>
                  save.mutate({ ...policy, require_approval: e.target.checked })
                }
              >
                Require approval
              </Checkbox>
              <Checkbox
                checked={policy.maker_checker}
                disabled={!policy.require_approval}
                onChange={(e) => save.mutate({ ...policy, maker_checker: e.target.checked })}
              >
                Maker-checker (no self-approval)
              </Checkbox>
            </Space>
        )}
      />
    </Card>
  );
}
