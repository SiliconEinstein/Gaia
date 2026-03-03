import { Descriptions, Tag, Card, Divider, Button, Space, message } from "antd";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Commit } from "../../api/commits";
import { reviewCommit, mergeCommit } from "../../api/commits";

const STATUS_COLORS: Record<string, string> = {
  pending_review: "orange",
  reviewed: "blue",
  merged: "green",
  rejected: "red",
};

interface Props {
  commit: Commit;
}

export function CommitDetail({ commit }: Props) {
  const queryClient = useQueryClient();

  const reviewMutation = useMutation({
    mutationFn: () => reviewCommit(commit.commit_id),
    onSuccess: () => {
      message.success("Review complete");
      queryClient.invalidateQueries({ queryKey: ["commits"] });
    },
    onError: (e) => message.error(String(e)),
  });

  const mergeMutation = useMutation({
    mutationFn: () => mergeCommit(commit.commit_id),
    onSuccess: () => {
      message.success("Merge complete");
      queryClient.invalidateQueries({ queryKey: ["commits"] });
    },
    onError: (e) => message.error(String(e)),
  });

  return (
    <Card>
      <Descriptions column={2} bordered size="small">
        <Descriptions.Item label="ID" span={2}>
          <code>{commit.commit_id}</code>
        </Descriptions.Item>
        <Descriptions.Item label="Status">
          <Tag color={STATUS_COLORS[commit.status] ?? "default"}>
            {commit.status}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="Message">{commit.message}</Descriptions.Item>
        <Descriptions.Item label="Operations">
          {commit.operations.length} operation(s)
        </Descriptions.Item>
        <Descriptions.Item label="Created">
          {commit.created_at ?? "—"}
        </Descriptions.Item>
      </Descriptions>

      <Space style={{ marginTop: 16 }}>
        {commit.status === "pending_review" && (
          <Button
            type="primary"
            loading={reviewMutation.isPending}
            onClick={() => reviewMutation.mutate()}
          >
            Review
          </Button>
        )}
        {commit.status === "reviewed" && (
          <Button
            type="primary"
            loading={mergeMutation.isPending}
            onClick={() => mergeMutation.mutate()}
            style={{ background: "#52c41a", borderColor: "#52c41a" }}
          >
            Merge
          </Button>
        )}
      </Space>

      {commit.check_results && (
        <>
          <Divider orientation="left">Validation Results</Divider>
          <pre style={{ fontSize: 12, background: "#f5f5f5", padding: 12, borderRadius: 6 }}>
            {JSON.stringify(commit.check_results, null, 2)}
          </pre>
        </>
      )}

      {commit.review_results && (
        <>
          <Divider orientation="left">Review Results</Divider>
          <pre style={{ fontSize: 12, background: "#f5f5f5", padding: 12, borderRadius: 6 }}>
            {JSON.stringify(commit.review_results, null, 2)}
          </pre>
        </>
      )}

      {commit.merge_results && (
        <>
          <Divider orientation="left">Merge Results</Divider>
          <pre style={{ fontSize: 12, background: "#f5f5f5", padding: 12, borderRadius: 6 }}>
            {JSON.stringify(commit.merge_results, null, 2)}
          </pre>
        </>
      )}
    </Card>
  );
}
