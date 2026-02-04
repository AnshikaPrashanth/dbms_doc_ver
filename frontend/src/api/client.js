import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:5000";

const client = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export default client;
