import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import VersionHistoryPanel from '../components/VersionHistoryPanel';

describe('VersionHistoryPanel', () => {
  it('calls restore with the selected version', async () => {
    const user = userEvent.setup();
    const handleRestore = vi.fn();

    render(
      <VersionHistoryPanel
        versions={[
          {
            version_id: 11,
            version_number: 3,
            created_by: 7,
            created_at: '2026-04-17T10:15:00Z',
            is_restore_version: false,
          },
        ]}
        isLoading={false}
        errorMessage=""
        canManageVersions
        onRefresh={vi.fn()}
        onRestoreVersion={handleRestore}
      />,
    );

    await user.click(screen.getByRole('button', { name: /Restore/i }));

    expect(handleRestore).toHaveBeenCalledWith(
      expect.objectContaining({ version_id: 11 }),
    );
  });

  it('disables restore when the user cannot manage versions', () => {
    render(
      <VersionHistoryPanel
        versions={[
          {
            version_id: 11,
            version_number: 3,
            created_by: 7,
            created_at: '2026-04-17T10:15:00Z',
            is_restore_version: false,
          },
        ]}
        isLoading={false}
        errorMessage=""
        canManageVersions={false}
        onRefresh={vi.fn()}
        onRestoreVersion={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /Restore/i })).toBeDisabled();
  });
});
