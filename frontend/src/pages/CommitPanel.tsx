import { useState } from "react";
import { List, Tag, Spin, Alert } from "antd";
import { useQuery } from "@tanstack/react-query";
import { fetchCommits } from "../api/commits";
import type { Commit } from "../api/commits";
import { CommitForm } from "../components/commit/CommitForm";
import { CommitDetail } from "../components/commit/CommitDetail";

const STATUS_COLORS: Record<string, string> = {
  pending_review: "orange",
  reviewed: "blue",
  merged: "green",
  rejected: "red",
};

export function CommitPanel() {
  const [selected, setSelected] = useState<Commit | null>(null);
  const { data: commits, isLoading, error } = useQuery({
    queryKey: ["commits"],
    queryFn: fetchCommits,
  });

  return (
    <div>
      <h2>Commits</h2>

      <CommitForm />

      {error && (
        <Alert type="error" message={String(error)} style={{ marginBottom: 16 }} />
      )}

      {isLoading && <Spin />}

      <List
        dataSource={commits ?? []}
        renderItem={(commit) => (
          <List.Item
            onClick={() => setSelected(selected?.commit_id === commit.commit_id ? null : commit)}
            style={{ cursor: "pointer", background: selected?.commit_id === commit.commit_id ? "#f0f5ff" : undefined }}
          >
            <List.Item.Meta
              title={
                <span>
                  <Tag color={STATUS_COLORS[commit.status] ?? "default"}>
                    {commit.status}
                  </Tag>
                  <code style={{ fontSize: 12 }}>{commit.commit_id.slice(0, 8)}</code>
                </span>
              }
              description={commit.message}
            />
            <span style={{ color: "#999", fontSize: 12 }}>
              {commit.operations.length} ops
            </span>
          </List.Item>
        )}
      />

      {selected && (
        <div style={{ marginTop: 16 }}>
          <CommitDetail commit={selected} />
        </div>
      )}
    </div>
  );
}
