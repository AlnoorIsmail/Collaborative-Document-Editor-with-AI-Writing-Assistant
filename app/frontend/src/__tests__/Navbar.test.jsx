import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import Navbar from '../components/Navbar';

const defaultProps = {
  title: 'Test Doc',
  onTitleChange: () => {},
  onSaveNow: () => {},
  onShare: () => {},
  onBack: () => {},
  onToggleAi: vi.fn(),
  isOwner: false,
  isReadOnly: false,
  isAiOpen: true,
  user: null,
};

function renderNavbar(saveStatus) {
  return render(
    <MemoryRouter>
      <Navbar {...defaultProps} saveStatus={saveStatus} />
    </MemoryRouter>
  );
}

describe('Navbar save status indicator', () => {
  it('shows "Saved" when saveStatus is saved', () => {
    renderNavbar('saved');
    expect(screen.getByText('Saved')).toBeInTheDocument();
  });

  it('shows "Saving…" when saveStatus is saving', () => {
    renderNavbar('saving');
    expect(screen.getByText('Saving…')).toBeInTheDocument();
  });

  it('shows "Unsaved changes" when saveStatus is unsaved', () => {
    renderNavbar('unsaved');
    expect(screen.getByText('Unsaved changes')).toBeInTheDocument();
  });

  it('shows "Save now" button only when unsaved', () => {
    const { rerender } = renderNavbar('unsaved');
    expect(screen.getByRole('button', { name: /save now/i })).toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <Navbar {...defaultProps} saveStatus="saved" />
      </MemoryRouter>
    );
    expect(screen.queryByRole('button', { name: /save now/i })).not.toBeInTheDocument();
  });

  it('shows the AI toggle label for the current sidebar state', () => {
    renderNavbar('saved');
    expect(screen.getByRole('button', { name: /hide ai/i })).toBeInTheDocument();
  });
});
