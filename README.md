# campuscom-partner-api

This project is the backend API for the partners of [campus4i.com](https://campus4i.com/) 

## Getting Started

1. The application is dependent on postgresql and mongodb server. If you are running the PostgreSQL MongoDB server from docker from the [campuscom-partner-api](https://github.com/campuscom/campuscom-partner-api) project, please configure your environment variables to use that server. Otherwise, you may configure them to use any server you like.
2. The application is configurable through environment variables. There is a `.env.example` file in the root folder. This file has all the configurable variables for the application. To quickly make your own configuration copy this file and name the copied file to `.env` and also put it in the root folder.
3. There is course provider api-key authentication and the API is accessible to anyone with the api-key.

## TOC

* [Change Log](docs/change_log.md)