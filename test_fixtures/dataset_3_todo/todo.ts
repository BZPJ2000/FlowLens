// Todo App - Simple
import { saveToStorage, loadFromStorage } from './storage';

export interface Todo {
  id: string;
  text: string;
  completed: boolean;
  createdAt: Date;
}

export function createTodo(text: string): Todo {
  const todo: Todo = {
    id: Date.now().toString(),
    text,
    completed: false,
    createdAt: new Date(),
  };
  const todos = loadFromStorage();
  todos.push(todo);
  saveToStorage(todos);
  return todo;
}

export function toggleTodo(id: string): void {
  const todos = loadFromStorage();
  const todo = todos.find(t => t.id === id);
  if (todo) {
    todo.completed = !todo.completed;
    saveToStorage(todos);
  }
}

export function deleteTodo(id: string): void {
  const todos = loadFromStorage();
  const filtered = todos.filter(t => t.id !== id);
  saveToStorage(filtered);
}

export function getTodos(): Todo[] {
  return loadFromStorage();
}
