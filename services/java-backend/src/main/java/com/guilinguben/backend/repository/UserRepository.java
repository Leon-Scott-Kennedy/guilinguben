package com.guilinguben.backend.repository;

import com.guilinguben.backend.model.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, String> {
    /** 登录查询：按用户名查用户（roles 为 EAGER 关联，一次查询带回角色集合） */
    Optional<User> findByUsername(String username);
}
