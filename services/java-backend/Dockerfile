# ============================================================
# Java 后端容器化（E 轮 16.42 方案丙可选资产，默认不启用）
# 多阶段构建：maven 编译 → temurin JRE 运行，镜像仅含 jar。
# 运行方式：docker compose up -d java-backend（见根 docker-compose.yml 注释块），
# 或单独构建：cd services/java-backend && docker build -t guilinguben-java .
# 环境变量（compose 已配置）：SPRING_DATASOURCE_URL / SPRING_DATA_REDIS_HOST /
#   AI_SERVICE_BASEURL 指向 host.docker.internal（覆盖 application.yml 的 localhost 默认值）。
# ============================================================

# ---- 构建阶段 ----
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
# 先拷贝 pom 并预拉依赖，利用 Docker 层缓存：pom 不变时依赖层复用
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests -B

# ---- 运行阶段 ----
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY --from=build /build/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
