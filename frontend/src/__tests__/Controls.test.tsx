import { useState } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { NumberInput, Select } from '@/components/ui';

const options = [{ value:'general',label:'通用受众' },{ value:'students',label:'大学生' },{ value:'disabled',label:'不可选受众',disabled:true }];

describe('Folio shared controls', () => {
  it('opens a custom menu, selects by keyboard and submits the selected form value', async () => {
    const user = userEvent.setup();
    render(<form aria-label="方案"><Select label="目标受众" name="audience" defaultValue="general" options={options} /></form>);
    const trigger = screen.getByRole('combobox',{ name:'目标受众' });
    expect(trigger.tagName).toBe('BUTTON');
    act(() => trigger.focus());
    await act(() => user.keyboard('{Enter}'));
    expect(screen.getByRole('listbox')).toHaveClass('folio-select-menu');
    expect(screen.getByRole('option',{name:'不可选受众'})).toHaveAttribute('aria-disabled','true');
    await act(() => user.keyboard('{ArrowDown}{Enter}'));
    await waitFor(() => expect(screen.queryByRole('listbox')).not.toBeInTheDocument());
    expect(trigger).toHaveTextContent('大学生');
    expect(trigger).toHaveFocus();
    expect(new FormData(screen.getByRole('form',{name:'方案'}) as HTMLFormElement).get('audience')).toBe('students');
  });

  it('closes on Escape without changing the value and respects disabled state', async () => {
    const user = userEvent.setup();
    const change = vi.fn();
    const view = render(<Select label="目标受众" value="general" onValueChange={change} options={options} />);
    const trigger = screen.getByRole('combobox',{name:'目标受众'});
    await act(() => user.click(trigger));
    await act(() => user.keyboard('{ArrowDown}{Escape}'));
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(change).not.toHaveBeenCalled();
    view.rerender(<Select label="目标受众" value="general" disabled onValueChange={change} options={options} />);
    await act(() => user.click(trigger));
    expect(trigger).toBeDisabled();
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('steps without submitting a form and disables the buttons at both page limits', async () => {
    const submit = vi.fn();
    const user = userEvent.setup();
    function Fixture() {
      const [value,setValue] = useState(1);
      return <form onSubmit={submit}><NumberInput label="演示页数" value={value} min={1} max={50} onValueChange={setValue} /></form>;
    }
    render(<Fixture />);
    const input = screen.getByRole('spinbutton',{name:'演示页数'});
    const minus = screen.getByRole('button',{name:'减少演示页数'});
    const plus = screen.getByRole('button',{name:'增加演示页数'});
    expect(minus).toBeDisabled();
    await act(() => user.click(plus));
    expect(input).toHaveValue(2);
    await act(() => user.click(minus));
    expect(input).toHaveValue(1);
    fireEvent.change(input,{target:{value:'49'}});
    await act(() => user.click(plus));
    expect(input).toHaveValue(50);
    expect(plus).toBeDisabled();
    expect(submit).not.toHaveBeenCalled();
  });

  it('allows editing, restores an empty value and normalizes values outside the bounds on blur', async () => {
    const user = userEvent.setup();
    function Fixture() {
      const [value,setValue] = useState(8);
      return <NumberInput label="演示页数" value={value} min={1} max={50} onValueChange={setValue} />;
    }
    render(<Fixture />);
    const input = screen.getByRole('spinbutton',{name:'演示页数'});
    await act(() => user.clear(input));
    expect(input).toHaveValue(null);
    await act(() => user.type(input,'12'));
    expect(input).toHaveValue(12);
    await act(() => user.clear(input));
    await act(() => user.tab());
    expect(input).toHaveValue(12);
    fireEvent.change(input,{target:{value:'100'}});
    fireEvent.blur(input);
    expect(input).toHaveValue(50);
    fireEvent.change(input,{target:{value:'0'}});
    fireEvent.blur(input);
    expect(input).toHaveValue(1);
    fireEvent.change(input,{target:{value:'3.6'}});
    fireEvent.blur(input);
    expect(input).toHaveValue(4);
  });

  it('honors disabled and read-only inputs and exact decimal steps', async () => {
    const user = userEvent.setup();
    const change = vi.fn();
    const view = render(<NumberInput label="数值" value={.2} min={0} max={1} step={.1} onValueChange={change} />);
    await act(() => user.click(screen.getByRole('button',{name:'增加数值'})));
    expect(change).toHaveBeenLastCalledWith(.3);
    view.rerender(<NumberInput label="数值" value={.3} disabled onValueChange={change} />);
    expect(screen.getByRole('spinbutton')).toBeDisabled();
    expect(screen.getByRole('button',{name:'增加数值'})).toBeDisabled();
    view.rerender(<NumberInput label="数值" value={.3} readOnly onValueChange={change} />);
    expect(screen.getByRole('button',{name:'减少数值'})).toBeDisabled();
    expect(screen.getByRole('spinbutton')).toHaveAttribute('readonly');
  });
});
