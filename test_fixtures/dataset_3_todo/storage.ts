// Storage for Todo
import { Todo } from './todo';
export function saveToStorage(todos: Todo[]): void { localStorage.setItem('todos', JSON.stringify(todos)); }
export function loadFromStorage(): Todo[] { return JSON.parse(localStorage.getItem('todos') || '[]'); }
