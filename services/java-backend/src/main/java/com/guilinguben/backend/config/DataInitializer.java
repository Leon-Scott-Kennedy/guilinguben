package com.guilinguben.backend.config;

import com.guilinguben.backend.model.Role;
import com.guilinguben.backend.model.User;
import com.guilinguben.backend.repository.RoleRepository;
import com.guilinguben.backend.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.util.HashSet;
import java.util.Set;

/**
 * 种子数据初始化（D 轮 16.40）：幂等创建角色与演示用户。
 * 生产环境应改为迁移脚本或独立管理接口创建用户；此处仅为本地演示启动即用。
 */
@Component
public class DataInitializer implements CommandLineRunner {

    private static final Logger logger = LoggerFactory.getLogger(DataInitializer.class);

    private final RoleRepository roleRepository;
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    public DataInitializer(RoleRepository roleRepository,
                           UserRepository userRepository,
                           PasswordEncoder passwordEncoder) {
        this.roleRepository = roleRepository;
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        // 幂等：角色已存在则复用；演示用户已存在则跳过（不动已改过的密码）
        Role adminRole = roleRepository.findByName("ADMIN").orElseGet(() ->
                roleRepository.save(createRole("ADMIN", "管理员：可访问全部接口与后续管理接口")));
        roleRepository.findByName("USER").orElseGet(() ->
                roleRepository.save(createRole("USER", "普通用户：业务问答接口")));

        if (userRepository.findByUsername("admin").isEmpty()) {
            User admin = new User();
            admin.setUsername("admin");
            admin.setPasswordHash(passwordEncoder.encode("admin123"));
            Set<Role> roles = new HashSet<>();
            roles.add(adminRole);
            admin.setRoles(roles);
            userRepository.save(admin);
            logger.info("种子用户已创建: admin（演示密码 admin123，role=ADMIN）");
        }
    }

    private Role createRole(String name, String description) {
        Role role = new Role();
        role.setName(name);
        role.setDescription(description);
        return role;
    }
}
